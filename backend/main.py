from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional
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
    "&models=best_match,ecmwf_ifs025"
    "&forecast_days=2"
    "&timezone=Europe%2FParis"
)

_meteo_cache: dict = {"data": None, "expires_at": None}
_meteo_lock = asyncio.Lock()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


def require_api_key(key: str = Security(api_key_header)):
    if not API_KEY or key != API_KEY:
        raise HTTPException(status_code=401, detail="Clé API invalide")
    return key


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="maison-temp", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/releve/{slug}", status_code=200)
async def post_releve(slug: str, payload: ReleverPayload, _: str = Depends(require_api_key)):
    async with get_db() as db:
        async with db.execute("SELECT id FROM sondes WHERE slug = ?", (slug,)) as cur:
            row = await cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Sonde '{slug}' inconnue")
        sonde_id = row[0]
        await db.execute(
            "INSERT INTO releves (sonde_id, temperature, humidite) VALUES (?, ?, ?)",
            (sonde_id, payload.temp, payload.hum),
        )
        await db.commit()
    return {"ok": True}


@app.get("/api/sondes", response_model=list[SondeOut])
async def get_sondes():
    async with get_db() as db:
        async with db.execute("SELECT id, slug, nom, actif FROM sondes ORDER BY id") as cur:
            sondes = await cur.fetchall()

        result = []
        for sonde_id, slug, nom, actif in sondes:
            async with db.execute(
                """SELECT temperature, humidite, recu_le FROM releves
                   WHERE sonde_id = ? ORDER BY recu_le DESC LIMIT 1""",
                (sonde_id,),
            ) as cur:
                row = await cur.fetchone()
            dernier = None
            if row:
                dernier = DernierReleve(
                    temperature=row[0],
                    humidite=row[1],
                    recu_le=datetime.fromisoformat(row[2]),
                )
            result.append(SondeOut(slug=slug, nom=nom, actif=actif, dernier_releve=dernier))
    return result


PERIOD_HOURS = {"24h": 24, "7d": 168, "30d": 720}


@app.get("/api/releves/{slug}", response_model=list[ReleverOut])
async def get_releves(slug: str, period: str = "24h"):
    if period not in PERIOD_HOURS:
        raise HTTPException(status_code=400, detail="Période invalide. Valeurs : 24h, 7d, 30d")
    since = datetime.now(timezone.utc) - timedelta(hours=PERIOD_HOURS[period])
    async with get_db() as db:
        async with db.execute("SELECT id FROM sondes WHERE slug = ?", (slug,)) as cur:
            row = await cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Sonde '{slug}' inconnue")
        sonde_id = row[0]
        async with db.execute(
            """SELECT temperature, humidite, recu_le FROM releves
               WHERE sonde_id = ? AND recu_le >= ?
               ORDER BY recu_le ASC""",
            (sonde_id, since.isoformat()),
        ) as cur:
            rows = await cur.fetchall()
    return [
        ReleverOut(
            temperature=r[0],
            humidite=r[1],
            recu_le=datetime.fromisoformat(r[2]),
        )
        for r in rows
    ]


@app.get("/api/meteo")
async def get_meteo():
    async with _meteo_lock:
        now = datetime.now(timezone.utc)
        if _meteo_cache["data"] and _meteo_cache["expires_at"] > now:
            return _meteo_cache["data"]
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(METEO_URL)
            resp.raise_for_status()
        _meteo_cache["data"] = resp.json()
        _meteo_cache["expires_at"] = now + timedelta(minutes=30)
    return _meteo_cache["data"]
