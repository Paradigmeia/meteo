import aiosqlite
from config import DATABASE_PATH
import os

SONDES_INITIALES = [
    ("chambre-parents", "Chambre parents", True),
    ("chambre-jade", "Chambre Jade", True),
    ("salon", "Salon", True),
    ("exterieur", "Extérieur", False),
]


def get_db():
    return aiosqlite.connect(DATABASE_PATH)


async def init_db():
    os.makedirs(os.path.dirname(os.path.abspath(DATABASE_PATH)), exist_ok=True)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS sondes (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                slug    TEXT NOT NULL UNIQUE,
                nom     TEXT NOT NULL,
                actif   BOOLEAN DEFAULT TRUE
            );

            CREATE TABLE IF NOT EXISTS releves (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                sonde_id     INTEGER NOT NULL REFERENCES sondes(id),
                temperature  REAL NOT NULL,
                humidite     REAL,
                recu_le      TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_releves_sonde_date ON releves(sonde_id, recu_le);
        """)
        for slug, nom, actif in SONDES_INITIALES:
            await db.execute(
                "INSERT OR IGNORE INTO sondes (slug, nom, actif) VALUES (?, ?, ?)",
                (slug, nom, actif),
            )
        await db.commit()
