from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import as_utc, month_bounds, now
from app.models.reservation import Reservation, ReservationStatus
from app.models.user import User


def is_blocked(user: User) -> bool:
    return user.blocked_until is not None and as_utc(user.blocked_until) > now()


def no_show_count(db: Session, user_id: int) -> int:
    """Neprezentarile din luna curenta (dupa 2 contul se blocheaza pana la finalul lunii)."""
    start, end = month_bounds(now())
    return db.scalar(
        select(func.count(Reservation.id)).where(
            Reservation.user_id == user_id,
            Reservation.status == ReservationStatus.NO_SHOW,
            Reservation.start_time >= start,
            Reservation.start_time < end,
        )
    )


def reservations_this_month(db: Session, user_id: int) -> int:
    """Rezervarile neanulate din luna curenta, cele care intra in limita de 3."""
    start, end = month_bounds(now())
    return db.scalar(
        select(func.count(Reservation.id)).where(
            Reservation.user_id == user_id,
            Reservation.status != ReservationStatus.CANCELLED,
            Reservation.start_time >= start,
            Reservation.start_time < end,
        )
    )


def user_view(db: Session, user: User) -> dict:
    """Utilizatorul in forma din Swagger (User), cu contoarele calculate."""
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "no_show_count": no_show_count(db, user.id),
        "blocked": is_blocked(user),
        "blocked_until": user.blocked_until,
        "reservations_this_month": reservations_this_month(db, user.id),
    }
