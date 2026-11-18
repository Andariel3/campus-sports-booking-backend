from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser
from app.db.session import get_db
from app.schemas.reservation import ReservationCreate, ReservationRead, reservation_view
from app.services import reservation_service
from app.services.reservation_service import ReservationError

router = APIRouter(prefix="/reservations", tags=["reservations"])

DbSession = Annotated[Session, Depends(get_db)]


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
