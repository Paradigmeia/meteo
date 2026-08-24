from pydantic import BaseModel, Field, field_validator
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

# L'humidité est écrêtée plutôt que rejetée dans une marge étroite autour de ses
# bornes physiques : un capteur en condensation peut rapporter 100,2 %, et un
# rejet ferait perdre le relevé définitivement — le Shelly n'émet qu'une fois,
# il ne réémet pas sur erreur. Au-delà de la marge, la valeur n'est plus une
# imprécision de mesure mais une aberration, et on rejette. La température, elle,
# est rejetée dès le dépassement : ses bornes (-100..100 °C) sont si larges qu'un
# dépassement ne peut pas être une imprécision.
HUM_TOLERANCE = 5.0
HUM_ACCEPT_MIN, HUM_ACCEPT_MAX = HUM_MIN - HUM_TOLERANCE, HUM_MAX + HUM_TOLERANCE


def clamp_humidity(value: Optional[float]) -> Optional[float]:
    """Ramène une humidité dans [0, 100]. `None` reste `None`."""
    if value is None:
        return None
    return min(HUM_MAX, max(HUM_MIN, value))


class ReleverPayload(BaseModel):
    temp: float = Field(allow_inf_nan=False, ge=TEMP_MIN, le=TEMP_MAX)
    hum: Optional[float] = Field(
        default=None, allow_inf_nan=False, ge=HUM_ACCEPT_MIN, le=HUM_ACCEPT_MAX
    )

    # mode "after" : les contraintes ge/le du champ sont appliquées avant, donc on
    # n'écrête que ce qui est déjà dans la marge d'acceptation.
    @field_validator("hum")
    @classmethod
    def _clamp_hum(cls, value: Optional[float]) -> Optional[float]:
        return clamp_humidity(value)


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
