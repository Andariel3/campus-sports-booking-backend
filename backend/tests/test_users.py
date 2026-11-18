from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.models.user import UserRole

USERS = "/api/v1/users"
RESOURCES = "/api/v1/resources"
COURT = {"name": "Teren tenis 1", "sport": "tenis"}


@pytest.mark.parametrize("role", [UserRole.STUDENT, UserRole.PROFESSOR])
def test_only_admin_can_change_resources(client: TestClient, make_user, role) -> None:
    _, headers = make_user(role)

    assert client.post(RESOURCES, json=COURT, headers=headers).status_code == 403
    assert client.patch(f"{RESOURCES}/1", json={}, headers=headers).status_code == 403
    response = client.delete(f"{RESOURCES}/1", headers=headers)
    assert response.status_code == 403
    assert response.json() == {"detail": "Nu aveti drepturi pentru aceasta operatie"}


def test_changing_resources_without_login_returns_401(client: TestClient) -> None:
    assert client.post(RESOURCES, json=COURT).status_code == 401


def test_anyone_can_read_resources(client: TestClient) -> None:
    assert client.get(RESOURCES).status_code == 200


def test_user_list_is_admin_only(client: TestClient, make_user) -> None:
    _, student = make_user(UserRole.STUDENT)
    assert client.get(USERS, headers=student).status_code == 403
    assert client.get(USERS).status_code == 401


def test_user_list_filters_by_role_and_blocked(client: TestClient, make_user, db) -> None:
    _, admin = make_user(UserRole.ADMINISTRATOR)
    student, _ = make_user(UserRole.STUDENT)
    blocked, _ = make_user(UserRole.STUDENT)
    make_user(UserRole.PROFESSOR)
    blocked.blocked_until = datetime.now(UTC) + timedelta(days=5)
    db.commit()

    everyone = client.get(USERS, headers=admin).json()
    assert len(everyone) == 4
    students = client.get(USERS, params={"role": "student"}, headers=admin).json()
    assert {u["id"] for u in students} == {student.id, blocked.id}
    assert [
        u["role"] for u in client.get(USERS, params={"role": "profesor"}, headers=admin).json()
    ] == ["profesor"]
    only_blocked = client.get(USERS, params={"blocked": "true"}, headers=admin).json()
    assert [u["id"] for u in only_blocked] == [blocked.id]
    assert only_blocked[0]["blocked"] is True
    not_blocked = client.get(USERS, params={"blocked": "false"}, headers=admin).json()
    assert blocked.id not in {u["id"] for u in not_blocked}
    assert client.get(USERS, params={"role": "Student"}, headers=admin).status_code == 422


def test_admin_unblocks_account(client: TestClient, make_user, db) -> None:
    _, admin = make_user(UserRole.ADMINISTRATOR)
    student, student_headers = make_user(UserRole.STUDENT)
    student.blocked_until = datetime.now(UTC) + timedelta(days=5)
    db.commit()

    response = client.post(f"{USERS}/{student.id}/unblock", headers=admin)

    assert response.status_code == 200
    assert response.json()["blocked"] is False
    db.refresh(student)
    assert student.blocked_until is None


def test_unblock_is_admin_only_and_404_for_missing_user(client: TestClient, make_user) -> None:
    student, student_headers = make_user(UserRole.STUDENT)
    _, admin = make_user(UserRole.ADMINISTRATOR)

    assert client.post(f"{USERS}/{student.id}/unblock", headers=student_headers).status_code == 403
    response = client.post(f"{USERS}/999/unblock", headers=admin)
    assert response.status_code == 404
    assert response.json() == {"detail": "Utilizatorul 999 nu exista"}


def test_expired_block_does_not_count(client: TestClient, make_user, db) -> None:
    student, headers = make_user(UserRole.STUDENT)
    student.blocked_until = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    assert client.get(f"{USERS}/me", headers=headers).json()["blocked"] is False
