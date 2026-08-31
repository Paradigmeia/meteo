from fastapi import FastAPI, HTTPException, Security, Depends, Query
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import logging
import secrets
import sqlite3
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

logger = logging.getLogger("maison-temp")

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
    """Agrège en Python. Chemin de repli de `_aggregate_sql` — cf. sa docstring.

    Reste la référence de comportement : c'est cette fonction que le test
    différentiel compare à la requête SQL, et elle sert encore pour de vrai
    quand SQLite ne sait pas dater une ligne.
    """
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


# Pendant SQL de `_finite_or_none` : une valeur non finie contaminerait la
# moyenne de tout le bucket, on l'écarte de l'accumulation comme une mesure
# absente (issue #36). `9e999` est la façon d'écrire l'infini en SQLite, donc
# `ABS(x) < 9e999` est faux pour ±inf et NULL pour NULL — deux cas qu'AVG et
# COUNT ignorent l'un comme l'autre. NaN n'a pas besoin d'être traité : SQLite
# ne sait pas le stocker et le relit en NULL (vérifié, cf. test dédié).
_FINI = "CASE WHEN ABS({c}) < 9e999 THEN {c} END"

# `FLOOR(x / bucket)` et non `x / bucket` : la division entière de SQLite
# tronque vers zéro, celle de Python (`//`) plancherise. Les deux coïncident sur
# des horodatages postérieurs à 1970 — les seuls que cette base contienne — mais
# pas avant, et reproduire `_aggregate` demande le plancher. Le paramètre est
# passé deux fois : en flottant pour forcer une division flottante, en entier
# pour remultiplier sans reperdre le type.
_AGGREGATE_SQL = f"""
    SELECT CAST(FLOOR(unixepoch(recu_le) / ?) AS INTEGER) * ? AS bucket,
           AVG({_FINI.format(c="temperature")}),
           AVG({_FINI.format(c="humidite")}),
           COUNT({_FINI.format(c="temperature")})
         + COUNT({_FINI.format(c="humidite")}) AS mesures
      FROM releves
     WHERE sonde_id = ? AND recu_le >= ? AND recu_le <= ?
  GROUP BY bucket
    HAVING mesures > 0
  ORDER BY bucket ASC
"""


async def _aggregate_sql(db, sonde_id, since, until, bucket_seconds):
    """Agrège en SQL. Renvoie `None` s'il faut se replier sur `_aggregate`.

    Raison d'être : `_aggregate` parcourait les lignes **dans le thread de la
    boucle d'événements**, sur un service mono-worker. Pendant ce temps la
    boucle ne traite rien d'autre, y compris les écritures du webhook Shelly —
    qui n'émet qu'une fois et ne réessaie pas (décision 6), donc un relevé
    perdu l'est définitivement (issue #67). Ici le parcours a lieu dans le
    thread d'aiosqlite, et SQLite relâche le GIL pendant `sqlite3_step` : le
    coût sort réellement de la boucle, ce qu'un `run_in_threadpool` autour du
    Python pur n'aurait pas fait.

    `HAVING mesures > 0` reproduit une propriété discrète de `_aggregate` : un
    bucket dont toutes les lignes ont leurs deux grandeurs absentes ou non
    finies n'y crée aucune entrée, parce que le `defaultdict` n'est touché que
    sous les deux `if`. Il ne doit donc pas apparaître ici non plus.

    L'arrondi reste en Python : `ROUND()` de SQLite arrondit à l'écart de zéro
    quand `round()` de Python arrondit au pair, et les deux divergent
    exactement sur les valeurs que produit une moyenne — `round(20.25, 1)` vaut
    20,2 en Python et 20,3 en SQL. Il n'y a au plus que quelques centaines de
    buckets, cet arrondi-là ne coûte rien à la boucle.

    Deux motifs de repli, tous deux journalisés — le repli refait le parcours
    Python et rend donc la boucle d'événements exactement au blocage que cette
    fonction existe pour supprimer. Il ne doit pas être silencieux :

    - **SQLite ne sait pas dater une ligne** là où `datetime.fromisoformat` y
      arrive : décalage sans deux-points (`+0000`, ce que produit
      `strftime('%z')`), virgule décimale, `t` minuscule. `unixepoch` rend NULL,
      ces lignes forment un groupe de clé NULL que `ORDER BY` place en tête.
      Une seule ligne de ce genre dans la plage suffit à faire retomber toute la
      requête sur le parcours Python ;
    - **la requête ne s'exécute pas** (`OperationalError`), cf. le garde
      ci-dessous.

    Aucune ligne du premier genre ne peut naître de l'application : `_now_iso`
    écrit toujours le même format. C'est un garde-fou contre une écriture
    directe en base, sur un endpoint public et non authentifié.

    Deux écarts connus face à `_aggregate`, tous deux assumés :

    - **la milliseconde.** SQLite date à la milliseconde et arrondit au plus
      proche, donc une sous-seconde ≥ 0,9995 s est lue comme la seconde
      suivante ; si cette seconde est une frontière de bucket, la ligne bascule
      dans le bucket voisin. Borné aux 500 dernières microsecondes avant une
      frontière. Sur les 8 188 relevés de production, une seule ligne porte une
      telle sous-seconde et aucune ne tombe sur une frontière. Cf.
      `test_agregation_sql_ecart_connu_sous_la_milliseconde` ;
    - **la sommation flottante.** `sum()` de Python accumule naïvement ; SQLite
      fait de même **jusqu'à la 3.43**, mais somme en Kahan-Babuška-Neumaier à
      partir de la **3.44**, ce qui rend une moyenne exactement arrondie. Les
      deux ne diffèrent que d'un ULP, mais un ULP suffit à faire basculer
      l'arrondi au dixième : mesuré sur la base de production, **17 buckets sur
      575** au pas de 3 h changent d'un dixième entre SQLite 3.40.1 et 3.51.1.
      Aucune implémentation Python unique ne peut coller aux deux versions —
      `math.fsum` colle exactement à la 3.51.1 et diverge de la 3.40.1 sur ces
      mêmes 17 buckets. `_aggregate` garde donc `sum()`, qui est ce que la
      production calcule aujourd'hui, et le test différentiel accepte l'une ou
      l'autre des deux valeurs plutôt que d'exiger une égalité qui ne survivrait
      pas à une montée de Debian. Cf. `test_agregation_sql_identique_au_python`.
    """
    try:
        async with db.execute(
            _AGGREGATE_SQL,
            (float(bucket_seconds), bucket_seconds, sonde_id, since, until),
        ) as cur:
            rows = await cur.fetchall()
    except sqlite3.OperationalError as exc:
        # Sans ce garde, une lecture agrégée répond 500 sur un endpoint public.
        # Le cas concret n'est pas théorique : `FLOOR()` fait partie des
        # fonctions mathématiques, **optionnelles à la compilation** de SQLite
        # (`SQLITE_ENABLE_MATH_FUNCTIONS`). Une bibliothèque assez récente pour
        # `unixepoch()` mais compilée sans elles ferait échouer toutes les
        # lectures agrégées, et seulement celles-là — les périodes de 12 h et
        # 24 h, qui ne passent pas par ici, continueraient de répondre 200.
        logger.warning(
            "agrégation SQL indisponible (%s) : repli sur le parcours Python, "
            "qui bloque la boucle d'événements (issue #67)", exc,
        )
        return None
    if rows and rows[0][0] is None:
        logger.warning(
            "sonde_id=%s : au moins une ligne de la plage porte un `recu_le` que "
            "SQLite ne sait pas dater ; repli sur le parcours Python, qui bloque "
            "la boucle d'événements (issue #67)", sonde_id,
        )
        return None
    return [
        ReleverOut(
            temperature=round(avg_temp, 1) if avg_temp is not None else None,
            humidite=round(avg_hum, 1) if avg_hum is not None else None,
            recu_le=datetime.fromtimestamp(bucket, tz=timezone.utc),
        )
        for bucket, avg_temp, avg_hum, _ in rows
    ]


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
            # Ramenées en UTC dès le parsing : le plafond ci-dessous et la
            # requête SQL raisonnent ainsi sur la même fenêtre. SQLite compare
            # `recu_le` comme du texte, et une borne portant un autre décalage
            # n'est pas ordonnée comme l'instant qu'elle désigne face aux lignes
            # en base, toutes écrites en `+00:00` par `_now_iso` (issue #59).
            start = _parse_recu_le(from_).astimezone(timezone.utc)
            end = _parse_recu_le(to).astimezone(timezone.utc)
        except ValueError:
            raise HTTPException(status_code=400, detail="Format de date invalide (ISO 8601 attendu)")
        except OverflowError:
            # `0001-01-01T00:00:00+14:00` est une date ISO parfaitement valide
            # dont la normalisation sort de `datetime.min`. Message distinct du
            # précédent : parler de format induirait l'appelant en erreur, il n'a
            # rien mal écrit. Sans ce garde, `astimezone` lève et l'endpoint —
            # public et non authentifié — répond 500.
            raise HTTPException(
                status_code=400,
                detail="Date hors des bornes représentables une fois ramenée en UTC "
                       "(année 1 à 9999)",
            )
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

    # Les deux bornes sont en UTC à ce stade — normalisées au parsing pour la
    # plage libre, `datetime.now(timezone.utc)` pour les périodes prédéfinies.
    # `isoformat()` rend donc `+00:00` et non `Z`, et c'est ce qui garde les
    # bornes comparables aux lignes en base : `Z` s'ordonnerait après le `.` des
    # microsecondes et exclurait la seconde de la borne basse. Cf. décision 22.
    since = start.isoformat()
    until = end.isoformat()
    async with get_db() as db:
        async with db.execute("SELECT id FROM sondes WHERE slug = ?", (slug,)) as cur:
            row = await cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Sonde '{slug}' inconnue")
        sonde_id = row[0]
        bucket = _bucket_seconds_for_range(hours)
        if bucket:
            agrege = await _aggregate_sql(db, sonde_id, since, until, bucket)
            if agrege is not None:
                return agrege
        async with db.execute(
            """SELECT temperature, humidite, recu_le FROM releves
               WHERE sonde_id = ? AND recu_le >= ? AND recu_le <= ?
               ORDER BY recu_le ASC""",
            (sonde_id, since, until),
        ) as cur:
            rows = await cur.fetchall()
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
