from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.clock import month_bounds
from app.models import Reservation, ReservationStatus, Resource, User, UserRole

URL = "/api/v1/reservations"
LOGIN = "/api/v1/auth/login"


def past_reservation(db: Session, user: User, resource: Resource, hours_ago: int) -> Reservation:
    """O rezervare care a inceput deja, in luna curenta."""
    start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    start -= timedelta(hours=hours_ago)
    month_start, _ = month_bounds(datetime.now(UTC))
    start = max(start, month_start)
    reservation = Reservation(
        user_id=user.id,
        resource_id=resource.id,
        start_time=start,
        end_time=start + timedelta(minutes=30),
        amount=Decimal("40"),
    )
    db.add(reservation)
    db.commit()
    return reservation


def no_show(client: TestClient, headers: dict, reservation_id: int):
    return client.post(f"{URL}/{reservation_id}/no-show", headers=headers)


def test_first_no_show_does_not_block(client: TestClient, make_user, court, db) -> None:
    student, student_headers = make_user(UserRole.STUDENT)
    _, admin = make_user(UserRole.ADMINISTRATOR)
    reservation = past_reservation(db, student, court, 1)

    response = no_show(client, admin, reservation.id)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "NEPREZENTARE"
    me = client.get("/api/v1/users/me", headers=student_headers).json()
    assert me["noShowCount"] == 1
    assert me["blocked"] is False


def test_second_no_show_blocks_until_next_month(client: TestClient, make_user, court, db) -> None:
    student, student_headers = make_user(UserRole.STUDENT)
    _, admin = make_user(UserRole.ADMINISTRATOR)
    first = past_reservation(db, student, court, 1)
    second = past_reservation(db, student, court, 2)
    no_show(client, admin, first.id)

    no_show(client, admin, second.id)

    db.refresh(student)
    _, next_month = month_bounds(datetime.now(UTC))
    assert student.blocked_until.replace(tzinfo=UTC) == next_month
    assert client.get("/api/v1/users/me", headers=student_headers).json()["blocked"] is True
    # cu contul blocat nu se mai poate loga, iar adminul il vede in lista de blocati
    login = client.post(LOGIN, data={"username": student.email, "password": "parola-buna-123"})
    assert login.status_code == 403
    blocked = client.get("/api/v1/users", params={"blocked": "true"}, headers=admin).json()
    assert [u["id"] for u in blocked] == [student.id]


def test_unblock_after_two_no_shows(client: TestClient, make_user, court, db) -> None:
    student, _ = make_user(UserRole.STUDENT)
    _, admin = make_user(UserRole.ADMINISTRATOR)
    for hours_ago in (1, 2):
        no_show(client, admin, past_reservation(db, student, court, hours_ago).id)

    client.post(f"/api/v1/users/{student.id}/unblock", headers=admin)

    login = client.post(LOGIN, data={"username": student.email, "password": "parola-buna-123"})
    assert login.status_code == 200


def test_no_show_rules(client: TestClient, make_user, court, db) -> None:
    student, student_headers = make_user(UserRole.STUDENT)
    _, admin = make_user(UserRole.ADMINISTRATOR)
    reservation = past_reservation(db, student, court, 1)

    assert no_show(client, student_headers, reservation.id).status_code == 403
    assert no_show(client, admin, 999).status_code == 404

    future = Reservation(
        user_id=student.id,
        resource_id=court.id,
        start_time=datetime.now(UTC) + timedelta(days=1),
        end_time=datetime.now(UTC) + timedelta(days=1, hours=1),
        amount=Decimal("40"),
    )
    db.add(future)
    db.commit()
    response = no_show(client, admin, future.id)
    assert response.status_code == 400
    assert response.json() == {"detail": "Rezervarea nu a inceput inca"}

    reservation.status = ReservationStatus.CANCELLED
    db.commit()
    assert no_show(client, admin, reservation.id).status_code == 400
