"""Schemele pentru resurse, in forma din Swagger (API REST (Swagger) din Confluence).

In JSON campurile sunt camelCase (pricePerHour, openHour, closeHour), in Python raman snake_case.
In baza de date sportul e in tabela sport_types, iar openHour/closeHour vin din
resource_schedules (acelasi program in fiecare zi a saptamanii).
"""

from datetime import time
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, model_validator
from pydantic.alias_generators import to_camel

from app.models.resource import POOL_SPORTS, ResourceType

HOUR_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"
DEFAULT_OPEN = "08:00"
DEFAULT_CLOSE = "22:00"

Money = Annotated[float, Field(ge=0, examples=[40])]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def type_for_sport(sport: str) -> ResourceType:
    return ResourceType.BAZIN if sport.strip().lower() in POOL_SPORTS else ResourceType.TEREN


def check_open_before_close(open_hour: str | None, close_hour: str | None) -> None:
    # "HH:MM" se compara corect ca text
    if open_hour and close_hour and open_hour >= close_hour:
        raise ValueError("openHour must be before closeHour")


class ResourceCreate(CamelModel):
    name: str = Field(min_length=2, max_length=150, examples=["Teren tenis 1"])
    # optional: se deduce din sport (inot = bazin, restul = teren).
    # daca e trimis, trebuie sa se potriveasca cu sportul
    type: ResourceType | None = None
    sport: str = Field(min_length=2, max_length=100, examples=["tenis"])
    description: str | None = Field(default=None, max_length=2000)
    price_per_hour: Money = 0
    open_hour: str = Field(default=DEFAULT_OPEN, pattern=HOUR_PATTERN, examples=["08:00"])
    close_hour: str = Field(default=DEFAULT_CLOSE, pattern=HOUR_PATTERN, examples=["22:00"])

    @model_validator(mode="after")
    def check_fields(self) -> Self:
        check_open_before_close(self.open_hour, self.close_hour)
        if self.type is not None and self.type != type_for_sport(self.sport):
            raise ValueError("type nu se potriveste cu sportul (bazin doar pentru inot)")
        return self


class ResourceUpdate(CamelModel):
    """Aceleasi campuri, toate optionale: se schimba doar ce se trimite."""

    name: str | None = Field(default=None, min_length=2, max_length=150)
    sport: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    price_per_hour: Money | None = None
    open_hour: str | None = Field(default=None, pattern=HOUR_PATTERN)
    close_hour: str | None = Field(default=None, pattern=HOUR_PATTERN)
    is_active: bool | None = None

    @model_validator(mode="after")
    def check_hours(self) -> Self:
        check_open_before_close(self.open_hour, self.close_hour)
        return self


HourText = Annotated[time | None, PlainSerializer(lambda t: t.strftime("%H:%M") if t else None)]


class ResourceRead(CamelModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: ResourceType
    sport: str
    description: str | None
    price_per_hour: float
    open_hour: HourText
    close_hour: HourText
    is_active: bool
