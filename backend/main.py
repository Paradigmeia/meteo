from fastapi import FastAPI, HTTPException, Security, Depends, Query
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import secrets
import httpx
import asyncio
import math

from config import API_KEY
from database import init_db, get_db
from models import (
    ReleverPayload, SondeOut, DernierReleve, ReleverOut,
    TEMP_MIN, TEMP_MAX, HUM_ACCEPT_MIN, HUM_ACCEPT_MAX, clamp_humidity,
)

METEO_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=43.3667&longitude=-1.5500"
    "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,weathercode"
    "&hourly=temperature_2m,precipitation_probability,weathercode"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weathercode"
    "&forecast_days=2"
    "&timezone=Europe%2FParis"
)

_meteo_cache: dict = {"data": None, "expires_at": None}
_meteo_lock = asyncio.Lock()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


def _key_is_valid(key: str) -> bool:
    """Comparaison à temps constant, tolérante à ce qui n'est pas une clé.

    `secrets.compare_digest` refuse les chaînes contenant du non-ASCII et lève
    une `TypeError` : lui passer la valeur reçue telle quelle transformait un
    refus en 500, sur un chemin d'authentification et sans être authentifié
    (issue #44). Comparer les encodages UTF-8 conserve la propriété de temps
    constant et traite une clé non-ASCII pour ce qu'elle est : une clé invalide.

    L'encodage ne peut pas échouer **pour les deux appelants actuels** : une
    séquence d'octets invalide dans une URL est remplacée par U+FFFD au
    décodage, et un en-tête est décodé en latin-1 — ni l'un ni l'autre ne
    produit de demi-codet isolé. Vérifié sur %ED%A0%80 et %FF%FE, qui donnent
    401 et non 500. Ce n'est pas une propriété de la fonction : un corps JSON,
    lui, peut porter un demi-codet isolé (cf. issue #62). Tout nouvel appelant
    doit donc revérifier cette hypothèse.

    L'entrée de l'appelant est le **premier** argument, le secret le second :
    compare_digest boucle sur la longueur du second, donc le nombre
    d'itérations ne dépend que du secret. Inverser l'ordre ferait dépendre le
    temps de réponse de la longueur envoyée par l'appelant.

    Le contrôle sur API_KEY vide est indispensable : sans lui, une installation
    dont la clé n'a pas été renseignée accepterait une clé vide.
    """
    if not API_KEY:
        return False
    return secrets.compare_digest(key.encode("utf-8"), API_KEY.encode("utf-8"))


def require_api_key(key: str = Security(api_key_header)):
    if not _key_is_valid(key):
        raise HTTPException(status_code=401, detail="Clé API invalide")
    return key


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_recu_le(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="maison-temp", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://meteo.paradigme.me"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _walk_non_finite(value, replace):
    """Parcourt une structure JSON et remplace les flottants non finis."""
    if isinstance(value, float) and not math.isfinite(value):
        return replace(value)
    if isinstance(value, dict):
        return {k: _walk_non_finite(v, replace) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_walk_non_finite(v, replace) for v in value]
    return value


def _json_safe(value):
    """Rend une structure sérialisable en conservant la trace du non-fini."""
    return _walk_non_finite(value, repr)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc: RequestValidationError):
    """Renvoie un 422 lisible même quand la valeur rejetée est non finie.

    Le gestionnaire par défaut recopie l'entrée fautive dans le corps de la
    réponse. Si c'est NaN ou ±inf, json.dumps lève et le client reçoit un 500
    opaque au lieu du 422 mérité — la validation a bien fait son travail, mais
    c'est le compte rendu de ce travail qui casse (issue #36).
    """
    return JSONResponse(
        status_code=422,
        content={"detail": _json_safe(jsonable_encoder(exc.errors()))},
    )


@app.get("/")
@app.get("/health")
async def health():
    return {"status": "ok"}


def _parse_shelly_value(value: str | None, low: float, high: float, label: str) -> float | None:
    """Convertit un paramètre de webhook Shelly en float, borné.

    Le firmware HTG3 sérialise ${ev.tC}/${ev.rh} en la chaîne littérale
    "null" quand ce champ est absent du rapport ayant déclenché l'action
    (ex: rapport déclenché par un changement de température, où ev.rh
    n'existe pas). On traite donc "null" comme une valeur absente plutôt
    que de rejeter la requête.

    `float()` accepte "nan", "inf" et "-inf" : sans le contrôle de finitude,
    ces valeurs entraient en base et faisaient ensuite échouer la sérialisation
    JSON de toute la réponse de lecture (issue #36). Les bornes écartent en plus
    l'aberrant, qui écraserait l'échelle des graphiques.
    """
    if value is None or value.strip().lower() in ("", "null"):
        return None
    try:
        parsed = float(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Valeur invalide : {value!r}")
    if not math.isfinite(parsed):
        raise HTTPException(status_code=422, detail=f"Valeur non finie : {value!r}")
    if not low <= parsed <= high:
        raise HTTPException(
            status_code=422,
            detail=f"{label} hors bornes ({low} à {high}) : {parsed}",
        )
    return parsed


def _finite_or_none(value: float | None) -> float | None:
    """Neutralise une valeur non finie lue en base.

    Les bornes à l'écriture empêchent d'en créer de nouvelles, mais une ligne
    écrite avant ce garde-fou reste possible — et une seule suffirait à faire
    échouer la sérialisation JSON de la réponse entière, pas seulement de la
    ligne fautive (issue #36). On la traite comme une mesure absente, exactement
    comme un relevé qui ne porte pas cette grandeur : le reste de la plage
    continue de s'afficher.
    """
    if value is None or not math.isfinite(value):
        return None
    return value


@app.get("/api/releve/{slug}", status_code=200)
async def get_releve(slug: str, key: str, temp: str | None = None, hum: str | None = None):
    """Endpoint GET pour les webhooks Shelly (URL action).
    Le Shelly H&T Gen3 envoie temp et humidité sur deux events distincts.
    Usage temp  : /api/releve/salon?temp=${ev.tC}&key=TOKEN
    Usage hum   : /api/releve/salon?hum=${ev.rh}&key=TOKEN
    """
    if not _key_is_valid(key):
        raise HTTPException(status_code=401, detail="Clé API invalide")
    temp_val = _parse_shelly_value(temp, TEMP_MIN, TEMP_MAX, "Température")
    hum_val = clamp_humidity(
        _parse_shelly_value(hum, HUM_ACCEPT_MIN, HUM_ACCEPT_MAX, "Humidité")
    )
    if temp_val is None and hum_val is None:
        raise HTTPException(status_code=422, detail="Au moins temp ou hum est requis")
    async with get_db() as db:
        async with db.execute("SELECT id FROM sondes WHERE slug = ?", (slug,)) as cur:
            row = await cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Sonde '{slug}' inconnue")
        sonde_id = row[0]
        await db.execute(
            "INSERT INTO releves (sonde_id, temperature, humidite, recu_le) VALUES (?, ?, ?, ?)",
            (sonde_id, temp_val, hum_val, _now_iso()),
        )
        await db.commit()
    return {"ok": True}


@app.post("/api/releve/{slug}", status_code=200)
async def post_releve(slug: str, payload: ReleverPayload, _: str = Depends(require_api_key)):
    async with get_db() as db:
        async with db.execute("SELECT id FROM sondes WHERE slug = ?", (slug,)) as cur:
            row = await cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Sonde '{slug}' inconnue")
        sonde_id = row[0]
        await db.execute(
            "INSERT INTO releves (sonde_id, temperature, humidite, recu_le) VALUES (?, ?, ?, ?)",
            (sonde_id, payload.temp, payload.hum, _now_iso()),
        )
        await db.commit()
    return {"ok": True}


@app.get("/api/sondes", response_model=list[SondeOut])
async def get_sondes():
    async with get_db() as db:
        async with db.execute(
            """SELECT s.slug, s.nom, s.actif,
                      rt.temperature, rt.recu_le AS recu_le_temp,
                      rh.humidite,    rh.recu_le AS recu_le_hum
               FROM sondes s
               LEFT JOIN releves rt ON rt.id = (
                   SELECT id FROM releves
                   WHERE sonde_id = s.id AND temperature IS NOT NULL
                   ORDER BY recu_le DESC LIMIT 1
               )
               LEFT JOIN releves rh ON rh.id = (
                   SELECT id FROM releves
                   WHERE sonde_id = s.id AND humidite IS NOT NULL
                   ORDER BY recu_le DESC LIMIT 1
               )
               WHERE s.actif = 1
               ORDER BY s.id"""
        ) as cur:
            rows = await cur.fetchall()

    result = []
    for slug, nom, actif, temp, recu_le_temp, hum, recu_le_hum in rows:
        dernier = None
        # Les deux grandeurs viennent de deux lignes distinctes : le Shelly les
        # envoie en deux actions séparées, et l'une peut cesser de remonter sans
        # l'autre. `recu_le` répond à « la sonde donne-t-elle encore signe de
        # vie ? » — c'est sur lui que le dashboard pose son badge « Hors ligne »
        # — donc c'est le plus récent des deux, pas celui de la température.
        # L'ancien code calculait ce maximum puis le jetait, et renvoyait
        # `recu_le_temp or recu_le_hum` : une sonde dont seule l'humidité remonte
        # encore paraissait figée et hors ligne (issue #43).
        #
        # La comparaison porte sur les datetime et non sur les chaînes ISO :
        # aujourd'hui toutes les lignes ont le même format, donc l'ordre
        # lexicographique coïncide avec l'ordre chronologique, mais rien ne le
        # garantit — `_parse_recu_le` ramène par exemple un horodatage naïf à
        # UTC, ce qu'une comparaison de chaînes ignorerait. Le `ORDER BY recu_le
        # DESC` de la requête ci-dessus, lui, reste lexicographique : c'est le
        # même sujet, côté SQL, et il est traité par l'issue #59.
        dt_temp = _parse_recu_le(recu_le_temp) if recu_le_temp else None
        dt_hum = _parse_recu_le(recu_le_hum) if recu_le_hum else None
        if dt_temp is not None or dt_hum is not None:
            dernier = DernierReleve(
                temperature=_finite_or_none(temp),
                humidite=_finite_or_none(hum),
                recu_le=max(dt for dt in (dt_temp, dt_hum) if dt is not None),
                # Exposés séparément : `recu_le` étant désormais un maximum, il
                # ne dit plus de quand date chaque grandeur, et la card a besoin
                # de cette information pour signaler celle des deux qui traîne.
                recu_le_temp=dt_temp,
                recu_le_hum=dt_hum,
            )
        result.append(SondeOut(slug=slug, nom=nom, actif=actif, dernier_releve=dernier))
    return result


PERIOD_HOURS = {"12h": 12, "24h": 24, "7d": 168, "30d": 720, "90d": 2160, "1an": 8760}

# Plafond de la plage libre (?from=&to=). Aligné sur la plus longue période
# prédéfinie : au-delà, l'appelant demanderait plus que ce que l'interface sait
# proposer. Sans ce plafond, ?from=1970-01-01&to=2100-01-01 fait lire toutes les
# lignes de la sonde et les agréger en mémoire, sans coût pour l'appelant et
# pour un résultat que personne ne regarde (issue #37). Le coût est modeste
# aujourd'hui — 8 090 relevés en base — mais il croît avec l'historique, et
# c'est une lecture non authentifiée.
MAX_RANGE_HOURS = PERIOD_HOURS["1an"]


def _bucket_seconds_for_range(hours: float) -> int | None:
    """Choisit la taille de bucket d'agrégation en fonction de l'étendue de la plage.

    Généralise la logique fixe par période (cf. PERIOD_BUCKET_SECONDS historique) pour
    couvrir aussi les plages libres (?from=&to=) de la vue Analyse, dont la durée n'est
    pas connue à l'avance.
    """
    if hours <= 24:
        return None
    if hours <= 168:
        return 10800
    if hours <= 720:
        return 43200
    if hours <= 2160:
        return 86400
    return 259200


def _aggregate(rows, bucket_seconds):
    buckets = defaultdict(lambda: {"temps": [], "hums": []})
    for temp, hum, recu_le_str in rows:
        dt = _parse_recu_le(recu_le_str)
        key = int(dt.timestamp() // bucket_seconds) * bucket_seconds
        # Une valeur non finie contaminerait la moyenne de tout le bucket : on
        # l'écarte de l'accumulation comme une mesure absente (issue #36).
        temp = _finite_or_none(temp)
        hum = _finite_or_none(hum)
        if temp is not None:
            buckets[key]["temps"].append(temp)
        if hum is not None:
            buckets[key]["hums"].append(hum)
    result = []
    for key in sorted(buckets.keys()):
        b = buckets[key]
        avg_temp = round(sum(b["temps"]) / len(b["temps"]), 1) if b["temps"] else None
        avg_hum = round(sum(b["hums"]) / len(b["hums"]), 1) if b["hums"] else None
        result.append(ReleverOut(
            temperature=avg_temp,
            humidite=avg_hum,
            recu_le=datetime.fromtimestamp(key, tz=timezone.utc),
        ))
    return result


@app.get("/api/releves/{slug}", response_model=list[ReleverOut])
async def get_releves(
    slug: str,
    period: str = "24h",
    from_: str | None = Query(None, alias="from"),
    to: str | None = None,
):
    """Plage soit par période prédéfinie (?period=), soit libre (?from=&to=, ISO 8601).

    La plage libre est utilisée par la vue Analyse (issue #19) pour couvrir les durées
    arbitraires et les sélections via date pickers, en plus des boutons rapides.
    """
    if from_ or to:
        if not from_ or not to:
            raise HTTPException(status_code=400, detail="from et to doivent être fournis ensemble")
        try:
            start = _parse_recu_le(from_)
            end = _parse_recu_le(to)
        except ValueError:
            raise HTTPException(status_code=400, detail="Format de date invalide (ISO 8601 attendu)")
        if end <= start:
            raise HTTPException(status_code=400, detail="'to' doit être postérieur à 'from'")
        hours = (end - start).total_seconds() / 3600
        if hours > MAX_RANGE_HOURS:
            raise HTTPException(
                status_code=400,
                # ceil et non round : à 365 j + 1 h, un arrondi affichait
                # « 365 jours demandés, maximum 365 jours » — un message qui se
                # contredit sur toute la zone la plus probable du dépassement
                detail=f"Plage trop large : {math.ceil(hours / 24)} jours demandés, "
                       f"maximum {MAX_RANGE_HOURS // 24} jours",
            )
    else:
        if period not in PERIOD_HOURS:
            raise HTTPException(status_code=400, detail="Période invalide. Valeurs : 12h, 24h, 7d, 30d, 90d, 1an")
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=PERIOD_HOURS[period])
        hours = PERIOD_HOURS[period]

    since = start.isoformat()
    until = end.isoformat()
    async with get_db() as db:
        async with db.execute("SELECT id FROM sondes WHERE slug = ?", (slug,)) as cur:
            row = await cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Sonde '{slug}' inconnue")
        sonde_id = row[0]
        async with db.execute(
            """SELECT temperature, humidite, recu_le FROM releves
               WHERE sonde_id = ? AND recu_le >= ? AND recu_le <= ?
               ORDER BY recu_le ASC""",
            (sonde_id, since, until),
        ) as cur:
            rows = await cur.fetchall()
    bucket = _bucket_seconds_for_range(hours)
    if bucket:
        return _aggregate(rows, bucket)
    return [
        ReleverOut(
            temperature=_finite_or_none(r[0]),
            humidite=_finite_or_none(r[1]),
            recu_le=_parse_recu_le(r[2]),
        )
        for r in rows
    ]


@app.get("/api/meteo")
async def get_meteo():
    async with _meteo_lock:
        now = datetime.now(timezone.utc)
        if _meteo_cache["data"] and _meteo_cache["expires_at"] > now:
            return _meteo_cache["data"]
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(METEO_URL)
                resp.raise_for_status()
            # json.loads accepte les littéraux NaN/Infinity : une réponse amont
            # empoisonnée serait mise en cache puis renverrait 500 à la
            # sérialisation, pendant les 30 minutes de validité du cache. On
            # neutralise avant de cacher, en valeur absente (issue #36).
            _meteo_cache["data"] = _walk_non_finite(resp.json(), lambda _: None)
            _meteo_cache["expires_at"] = now + timedelta(minutes=30)
        except Exception:
            if _meteo_cache["data"]:
                return _meteo_cache["data"]
            raise HTTPException(status_code=502, detail="Service météo indisponible")
    return _meteo_cache["data"]
