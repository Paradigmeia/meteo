from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ReleverPayload(BaseModel):
    temp: float
    hum: Optional[float] = None


class DernierReleve(BaseModel):
    temperature: Optional[float]
    humidite: Optional[float]
    recu_le: Optional[datetime]
    recu_le_hum: Optional[datetime] = None


class SondeOut(BaseModel):
    slug: str
    nom: str
    actif: bool
    dernier_releve: Optional[DernierReleve]


class ReleverOut(BaseModel):
    temperature: Optional[float]
    humidite: Optional[float]
    recu_le: datetime
