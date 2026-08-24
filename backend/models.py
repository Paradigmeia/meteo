from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# Bornes physiques plausibles pour une sonde domestique. Elles servent surtout de
# garde-fou contre les valeurs non finies : Pydantic accepte NaN et ±inf par défaut
# pour un `float`, et une seule ligne non finie en base suffit à faire échouer la
# sérialisation JSON de TOUTE une réponse de lecture, pas seulement de la ligne
# fautive (issue #36). Volontairement larges : la sonde Shelly H&T Gen3 couvre
# -40..60 °C, l'objectif est d'écarter l'aberrant, pas de valider la métrologie.
TEMP_MIN, TEMP_MAX = -100.0, 100.0
HUM_MIN, HUM_MAX = 0.0, 100.0


class ReleverPayload(BaseModel):
    temp: float = Field(allow_inf_nan=False, ge=TEMP_MIN, le=TEMP_MAX)
    hum: Optional[float] = Field(default=None, allow_inf_nan=False, ge=HUM_MIN, le=HUM_MAX)


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
