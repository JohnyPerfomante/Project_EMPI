from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from conftest import get, send
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import settings
from app.database.session import session
from app.main import app
from app.models import AuditLog, CourseMembership, TeacherCourse, User
from app.security.auth import verify_password

pytestmark = pytest.mark.postgres
PASSWORD = "Registration-test-2026!"


def registration_body(role="student", email="new-user@example.org"):
    return {
        "full_name": "  Тетяна Коваленко  ",
        "email": email,
        "role": role,
        "password": PASSWORD,
        "password_confirmation": PASSWORD,
    }


@pytest.mark.parametrize("role", ["student", "teacher"])
def test_new_account_can_login_with_selected_role_and_has_no_course_access(clients, school, role):
    anonymous = clients["anonymous"]
    body = registration_body(role, "New-User@EXAMPLE.ORG")
    user = send(anonymous, "/auth/register", body, 201)
    assert user["full_name"] == "Тетяна Коваленко"
    assert user["email"] == "new-user@example.org"
    assert user["role"] == role and user["active"] is True and user["demo"] is False
    assert "password" not in user and "password_hash" not in user
    get(anonymous, "/auth/me", 401)
    with session() as db:
        account = db.get(User, user["id"])
        assert account.password_hash != PASSWORD
        assert verify_password(PASSWORD, account.password_hash)
        event = db.scalar(
            select(AuditLog).where(AuditLog.action == "register", AuditLog.entity_id == account.id)
        )
        assert event.details == {"role": role}
        assert (
            db.scalar(
                select(func.count())
                .select_from(CourseMembership)
                .where(
                    CourseMembership.student_id == account.id,
                )
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(TeacherCourse)
                .where(
                    TeacherCourse.teacher_id == account.id,
                )
            )
            == 0
        )
    send(anonymous, "/auth/login", {"email": body["email"], "password": PASSWORD})
    assert get(anonymous, "/auth/me")["id"] == user["id"]
    assert get(anonymous, "/courses")["total"] == 0
    get(anonymous, f"/courses/{school['id']}", 404)
    get(anonymous, "/users", 403)
    send(anonymous, "/auth/logout")
    send(anonymous, "/auth/login", {"email": user["email"], "password": PASSWORD})


@pytest.mark.parametrize(
    "changes",
    [
        {"role": "admin"},
        {"active": False},
        {"demo": True},
        {"password": "short", "password_confirmation": "short"},
        {"password_confirmation": "Different-password-2026!"},
        {"email": "invalid-email"},
        {"full_name": "  "},
        {"full_name": "Ім’я\x00Прізвище"},
    ],
)
def test_registration_rejects_invalid_data_without_creating_account(pg, changes):
    with TestClient(app, headers={"X-EMPI-Request": "1"}) as client:
        send(client, "/auth/register", registration_body() | changes, 422)
    with session() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0


def test_duplicate_email_preserves_existing_account(clients):
    anonymous = clients["anonymous"]
    response = send(anonymous, "/auth/register", registration_body("teacher", "STUDENT@EXAMPLE.ORG"), 409)
    assert response["error"]["code"] == "email_already_registered"
    result = send(anonymous, "/auth/login", {"email": "student@example.org", "password": clients["password"]})
    assert result["id"] == clients["student_id"] and result["role"] == "student"


def test_concurrent_registration_creates_one_account(pg):
    ready = Barrier(2)

    def register():
        with TestClient(app, headers={"X-EMPI-Request": "1"}) as client:
            ready.wait(timeout=10)
            return client.post("/api/v1/auth/register", json=registration_body()).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: register(), range(2))) == [201, 409]
    with session() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
        assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "register")) == 1


def test_registration_throttle_and_csrf_protection(pg, monkeypatch):
    monkeypatch.setattr(settings(), "registration_limit", 2)
    with TestClient(app) as client:
        assert client.post("/api/v1/auth/register", json=registration_body()).status_code == 403
        client.headers["X-EMPI-Request"] = "1"
        send(client, "/auth/register", registration_body(), 201)
        send(client, "/auth/register", registration_body(), 409)
        send(client, "/auth/register", registration_body(), 429)
        send(client, "/auth/login", {"email": "new-user@example.org", "password": PASSWORD})
