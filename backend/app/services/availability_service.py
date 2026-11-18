"""Orarul unei resurse pe o zi: intervale de cate o ora, libere, ocupate sau in mentenanta."""

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import as_utc, local_datetime
from app.models.maintenance_block import MaintenanceBlock
from app.models.reservation import Reservation, ReservationStatus
from app.models.resource import Resource

SLOT = timedelta(hours=1)


def overlapping_reservations(
    db: Session, resource_id: int, start: datetime, end: datetime
) -> list[Reservation]:
    """Rezervarile neanulate care se suprapun cu [start, end)."""
    return list(
        db.scalars(
            select(Reservation).where(
                Reservation.resource_id == resource_id,
                Reservation.status != ReservationStatus.CANCELLED,
                Reservation.start_time < end,
                Reservation.end_time > start,
            )
        )
    )


def overlapping_blocks(
    db: Session, resource_id: int, start: datetime, end: datetime
) -> list[MaintenanceBlock]:
    return list(
        db.scalars(
            select(MaintenanceBlock).where(
                MaintenanceBlock.resource_id == resource_id,
                MaintenanceBlock.start_time < end,
                MaintenanceBlock.end_time > start,
            )
        )
    )


def opening_hours(resource: Resource, day: date) -> tuple[datetime, datetime] | None:
    """Ora de deschidere si de inchidere pentru ziua respectiva, in UTC (None daca e inchis)."""
    schedule = resource.schedule_for(day.weekday())
    if schedule is None:
        return None
    return local_datetime(day, schedule.open_time), local_datetime(day, schedule.close_time)


def day_slots(db: Session, resource: Resource, day: date) -> list[dict]:
    hours = opening_hours(resource, day) if resource.is_active else None
    if hours is None:
        return []
    opens, closes = hours

    reservations = overlapping_reservations(db, resource.id, opens, closes)
    blocks = overlapping_blocks(db, resource.id, opens, closes)

    slots = []
    start = opens
    while start + SLOT <= closes:
        end = start + SLOT
        if _overlaps(blocks, start, end):
            status = "mentenanta"
        elif _overlaps(reservations, start, end):
            status = "ocupat"
        else:
            status = "liber"
        slots.append({"start": start, "end": end, "status": status})
        start = end
    return slots


def _overlaps(items: list, start: datetime, end: datetime) -> bool:
    return any(as_utc(i.start_time) < end and as_utc(i.end_time) > start for i in items)
