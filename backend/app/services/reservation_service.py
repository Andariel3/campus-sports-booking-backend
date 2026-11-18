"""Rezervarile si regulile din regulamentul USV."""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import LOCAL_TZ, month_bounds, now
from app.models.reservation import Reservation, ReservationStatus
from app.models.resource import Resource
from app.models.user import User, UserRole
from app.schemas.reservation import ReservationCreate, to_utc
from app.services import availability_service, user_service

MAX_DAYS_AHEAD = 14
MAX_PER_MONTH_FOR_STUDENTS = 3


class ReservationError(Exception):
    """O regula incalcata. status_code e codul HTTP din Swagger."""

    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidInterval(ReservationError):
    status_code = 400


class NotAllowed(ReservationError):
    status_code = 403


class SlotTaken(ReservationError):
    status_code = 409


class NotFound(ReservationError):
    status_code = 404


def create_reservation(db: Session, user: User, data: ReservationCreate) -> Reservation:
    start, end = to_utc(data.start), to_utc(data.end)

    resource = db.get(Resource, data.resource_id)
    if resource is None:
        raise NotFound(f"Resursa {data.resource_id} nu exista")
    if not resource.is_active:
        raise InvalidInterval("Resursa nu se mai poate rezerva")

    _check_interval(resource, start, end)

    # blocam randul utilizatorului pana la commit, ca doua cereri simultane ale aceluiasi
    # student sa nu treaca amandoua de limita de 3 (pe postgres; sqlite ignora)
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    _check_user_can_book(db, user, start)

    if availability_service.overlapping_blocks(db, resource.id, start, end):
        raise SlotTaken("Intervalul este blocat pentru mentenanta")
    if availability_service.overlapping_reservations(db, resource.id, start, end):
        raise SlotTaken("Intervalul este deja ocupat")

    hours = Decimal((end - start).total_seconds()) / Decimal(3600)
    reservation = Reservation(
        user_id=user.id,
        resource_id=resource.id,
        start_time=start,
        end_time=end,
        amount=(resource.price_per_hour * hours).quantize(Decimal("0.01")),
    )
    db.add(reservation)
    try:
        db.commit()
    except IntegrityError:
        # constrangerea prevent_overlapping_bookings din postgres: cineva a rezervat
        # acelasi interval intre verificarea de mai sus si commit
        db.rollback()
        raise SlotTaken("Intervalul este deja ocupat") from None
    db.refresh(reservation)
    return reservation


def _check_interval(resource: Resource, start, end) -> None:
    if start >= end:
        raise InvalidInterval("Ora de sfarsit trebuie sa fie dupa ora de inceput")
    if start.minute or start.second or end.minute or end.second:
        raise InvalidInterval("Rezervarile se fac pe ore fixe (de ex. 18:00 - 19:00)")
    if start < now():
        raise InvalidInterval("Nu se poate rezerva in trecut")
    if start > now() + timedelta(days=MAX_DAYS_AHEAD):
        raise InvalidInterval(f"Se poate rezerva cu maxim {MAX_DAYS_AHEAD} zile inainte")

    day = start.astimezone(LOCAL_TZ).date()
    hours = availability_service.opening_hours(resource, day)
    if hours is None or start < hours[0] or end > hours[1]:
        raise InvalidInterval("Intervalul este in afara programului resursei")


def _check_user_can_book(db: Session, user: User, start) -> None:
    if user_service.is_blocked(user):
        raise NotAllowed("Contul este blocat din cauza neprezentarilor")
    if user.role != UserRole.STUDENT:
        # limita de 3 pe luna e doar pentru studenti (PRD)
        return
    month_start, month_end = month_bounds(start)
    count = db.scalar(
        select(func.count(Reservation.id)).where(
            Reservation.user_id == user.id,
            Reservation.status != ReservationStatus.CANCELLED,
            Reservation.start_time >= month_start,
            Reservation.start_time < month_end,
        )
    )
    if count >= MAX_PER_MONTH_FOR_STUDENTS:
        raise NotAllowed(f"Ai atins limita de {MAX_PER_MONTH_FOR_STUDENTS} rezervari pe luna")
