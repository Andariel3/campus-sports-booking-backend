"""Rezervarile in forma din Swagger.

In baza de date statusul e Confirmed / Cancelled / NoShow si plata e is_paid.
In API (Swagger) statusul e ACTIVA / ANULATA / FINALIZATA / NEPREZENTARE si plata ACHITATA /
NEACHITATA. FINALIZATA nu e in baza: e o rezervare Confirmed al carei interval s-a terminat.
"""

from datetime import datetime
from enum import StrEnum

from app.core.clock import LOCAL_TZ, as_utc, now
from app.models.reservation import Reservation, ReservationStatus
from app.schemas.resource import CamelModel, ResourceRead


class ApiStatus(StrEnum):
    ACTIVA = "ACTIVA"
    ANULATA = "ANULATA"
    FINALIZATA = "FINALIZATA"
    NEPREZENTARE = "NEPREZENTARE"


class PaymentStatus(StrEnum):
    ACHITATA = "ACHITATA"
    NEACHITATA = "NEACHITATA"


def api_status(reservation: Reservation) -> ApiStatus:
    if reservation.status == ReservationStatus.CANCELLED:
        return ApiStatus.ANULATA
    if reservation.status == ReservationStatus.NO_SHOW:
        return ApiStatus.NEPREZENTARE
    if as_utc(reservation.end_time) <= now():
        return ApiStatus.FINALIZATA
    return ApiStatus.ACTIVA


def to_utc(value: datetime) -> datetime:
    """O ora fara fus orar (ca in exemplul din Swagger) e ora Romaniei."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=LOCAL_TZ)
    return as_utc(value)


class ReservationCreate(CamelModel):
    resource_id: int
    start: datetime
    end: datetime


class ReservationRead(CamelModel):
    id: int
    user_id: int
    resource: ResourceRead
    start: datetime
    end: datetime
    status: ApiStatus
    payment_status: PaymentStatus
    amount: float
    created_at: datetime | None


def reservation_view(reservation: Reservation) -> dict:
    return {
        "id": reservation.id,
        "user_id": reservation.user_id,
        "resource": ResourceRead.model_validate(reservation.resource),
        "start": as_utc(reservation.start_time),
        "end": as_utc(reservation.end_time),
        "status": api_status(reservation),
        "payment_status": PaymentStatus.ACHITATA
        if reservation.is_paid
        else PaymentStatus.NEACHITATA,
        "amount": float(reservation.amount),
        "created_at": as_utc(reservation.created_at) if reservation.created_at else None,
    }
