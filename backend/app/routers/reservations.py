from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.core.deps import AdminUser, CurrentUser
from app.db.session import get_db
from app.schemas.reservation import (
    ApiStatus,
    PaymentUpdate,
    ReservationCreate,
    ReservationRead,
    reservation_view,
)
from app.services import reservation_service
from app.services.reservation_service import ReservationError

router = APIRouter(prefix="/reservations", tags=["reservations"])

DbSession = Annotated[Session, Depends(get_db)]
ReservationId = Annotated[int, Path(alias="reservationId")]


@router.get(
    "",
    response_model=list[ReservationRead],
    summary="Lista rezervarilor",
    description="Studentii si profesorii vad doar rezervarile proprii. Adminul le vede pe toate.",
)
def list_reservations(
    user: CurrentUser,
    db: DbSession,
    status_filter: Annotated[ApiStatus | None, Query(alias="status")] = None,
    resource_id: Annotated[int | None, Query(alias="resourceId")] = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
):
    reservations = reservation_service.list_reservations(
        db, user, status_filter, resource_id, date_from, date_to
    )
    return [reservation_view(r) for r in reservations]


@router.post(
    "",
    response_model=ReservationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Creare rezervare",
    description=(
        "Reguli: intervalul liber si neblocat (409), pe ore fixe, in programul resursei si "
        "cu maxim 14 zile inainte (400), maxim 3 rezervari pe luna pentru studenti si cont "
        "neblocat (403). O ora fara fus orar e considerata ora Romaniei."
    ),
)
def create_reservation(data: ReservationCreate, user: CurrentUser, db: DbSession):
    try:
        reservation = reservation_service.create_reservation(db, user, data)
    except ReservationError as exc:
        raise HTTPException(exc.status_code, exc.message) from None
    return reservation_view(reservation)


@router.get("/{reservationId}", response_model=ReservationRead, summary="Detalii rezervare")
def get_reservation(reservation_id: ReservationId, user: CurrentUser, db: DbSession):
    try:
        reservation = reservation_service.get_reservation(db, user, reservation_id)
    except ReservationError as exc:
        raise HTTPException(exc.status_code, exc.message) from None
    return reservation_view(reservation)


@router.delete(
    "/{reservationId}",
    response_model=ReservationRead,
    summary="Anulare rezervare",
    description=(
        "Rezervarea nu se sterge, ci trece in statusul ANULATA. Utilizatorul poate anula "
        "cu minim 2 ore inainte. Adminul poate anula oricand."
    ),
)
def cancel_reservation(reservation_id: ReservationId, user: CurrentUser, db: DbSession):
    try:
        reservation = reservation_service.cancel_reservation(db, user, reservation_id)
    except ReservationError as exc:
        raise HTTPException(exc.status_code, exc.message) from None
    return reservation_view(reservation)


@router.patch(
    "/{reservationId}/payment",
    response_model=ReservationRead,
    tags=["payments"],
    summary="Marcare plata (admin)",
    description="Adminul marcheaza rezervarea ca ACHITATA sau NEACHITATA.",
)
def set_payment(reservation_id: ReservationId, data: PaymentUpdate, _: AdminUser, db: DbSession):
    try:
        reservation = reservation_service.set_payment(db, reservation_id, data.payment_status)
    except ReservationError as exc:
        raise HTTPException(exc.status_code, exc.message) from None
    return reservation_view(reservation)


@router.post(
    "/{reservationId}/no-show",
    response_model=ReservationRead,
    summary="Marcare neprezentare (admin)",
    description=(
        "Rezervarea trece in NEPREZENTARE. La a doua neprezentare din luna contul "
        "utilizatorului se blocheaza pana la inceputul lunii urmatoare."
    ),
)
def mark_no_show(reservation_id: ReservationId, _: AdminUser, db: DbSession):
    try:
        reservation = reservation_service.mark_no_show(db, reservation_id)
    except ReservationError as exc:
        raise HTTPException(exc.status_code, exc.message) from None
    return reservation_view(reservation)
