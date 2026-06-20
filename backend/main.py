from fastapi import FastAPI, HTTPException, Security, Depends, Query
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import secrets
import httpx
import asyncio

from config import API_KEY
from database import init_db, get_db
from models import ReleverPayload, SondeOut, DernierReleve, ReleverOut

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


def require_api_key(key: str = Security(api_key_header)):
    if not API_KEY or not secrets.compare_digest(key, API_KEY):
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


@app.get("/")
@app.get("/health")
async def health():
    return {"status": "ok"}


def _parse_shelly_value(value: str | None) -> float | None:
    """Convertit un paramètre de webhook Shelly en float.

    Le firmware HTG3 sérialise ${ev.tC}/${ev.rh} en la chaîne littérale
    "null" quand ce champ est absent du rapport ayant déclenché l'action
    (ex: rapport déclenché par un changement de température, où ev.rh
    n'existe pas). On traite donc "null" comme une valeur absente plutôt
    que de rejeter la requête.
    """
    if value is None or value.strip().lower() in ("", "null"):
        return None
    try:
        return float(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Valeur invalide : {value!r}")


@app.get("/api/releve/{slug}", status_code=200)
async def get_releve(slug: str, key: str, temp: str | None = None, hum: str | None = None):
    """Endpoint GET pour les webhooks Shelly (URL action).
    Le Shelly H&T Gen3 envoie temp et humidité sur deux events distincts.
    Usage temp  : /api/releve/salon?temp=${ev.tC}&key=TOKEN
    Usage hum   : /api/releve/salon?hum=${ev.rh}&key=TOKEN
    """
    if not API_KEY or not secrets.compare_digest(key, API_KEY):
        raise HTTPException(status_code=401, detail="Clé API invalide")
    temp_val = _parse_shelly_value(temp)
    hum_val = _parse_shelly_value(hum)
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
        recu_le = recu_le_temp or recu_le_hum
        if recu_le is not None:
            # Prend le timestamp le plus récent des deux
            if recu_le_temp and recu_le_hum:
                recu_le = recu_le_temp if recu_le_temp > recu_le_hum else recu_le_hum
            dernier = DernierReleve(
                temperature=temp,
                humidite=hum,
                recu_le=_parse_recu_le(recu_le_temp or recu_le_hum),
                recu_le_hum=_parse_recu_le(recu_le_hum) if recu_le_hum else None,
            )
        result.append(SondeOut(slug=slug, nom=nom, actif=actif, dernier_releve=dernier))
    return result


PERIOD_HOURS = {"12h": 12, "24h": 24, "7d": 168, "30d": 720, "90d": 2160, "1an": 8760}


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
        ReleverOut(temperature=r[0], humidite=r[1], recu_le=_parse_recu_le(r[2]))
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
            _meteo_cache["data"] = resp.json()
            _meteo_cache["expires_at"] = now + timedelta(minutes=30)
        except Exception:
            if _meteo_cache["data"]:
                return _meteo_cache["data"]
            raise HTTPException(status_code=502, detail="Service météo indisponible")
    return _meteo_cache["data"]
