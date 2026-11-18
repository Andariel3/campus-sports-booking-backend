import datetime as dt
from typing import Literal

from app.schemas.resource import CamelModel


class Slot(CamelModel):
    start: dt.datetime
    end: dt.datetime
    status: Literal["liber", "ocupat", "mentenanta"]


class Availability(CamelModel):
    resource_id: int
    date: dt.date
    slots: list[Slot]
