import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

DATABASE = os.getenv("TEST_DATABASE_URL")
if DATABASE:
    if not (make_url(DATABASE).database or "").endswith("_test"):
        raise RuntimeError("TEST_DATABASE_URL must target a disposable database ending in _test")
    os.environ.update(APP_ENV="test", DATABASE_URL=DATABASE, NLP_PROVIDER="test", COOKIE_SECURE="false")

from app.database.session import engine  # noqa: E402


@pytest.fixture(scope="session")
def migrated():
    if not DATABASE:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")
    yield


@pytest.fixture
def pg(migrated):
    from app.models import Base

    with engine().begin() as connection:
        names = ", ".join(connection.dialect.identifier_preparer.quote(name) for name in Base.metadata.tables)
        connection.execute(text(f"TRUNCATE {names} RESTART IDENTITY"))


@pytest.fixture
def clients(pg):
    from contextlib import ExitStack

    from app.database.session import session
    from app.main import app
    from app.models import Role, User
    from app.security.auth import password_hasher

    password = "Fixture-only-password-95!"
    hashed = password_hasher.hash(password)
    with session() as db, db.begin():
        for key, role in (
            ("admin", Role.ADMIN),
            ("teacher", Role.TEACHER),
            ("outsider", Role.TEACHER),
            ("student", Role.STUDENT),
            ("student2", Role.STUDENT),
        ):
            db.add(User(full_name=key.title(), email=f"{key}@example.org", role=role, password_hash=hashed))
    with ExitStack() as stack:
        anonymous = stack.enter_context(TestClient(app, headers={"X-EMPI-Request": "1"}))
        result = {"anonymous": anonymous, "password": password}
        for key in ("admin", "teacher", "outsider", "student", "student2"):
            client = stack.enter_context(TestClient(app, headers={"X-EMPI-Request": "1"}))
            response = client.post(
                "/api/v1/auth/login", json={"email": f"{key}@example.org", "password": password}
            )
            assert response.status_code == 200, response.text
            result[key] = client
            result[key + "_id"] = response.json()["id"]
        yield result


def get(client, path, expected=200):
    response = client.get("/api/v1" + path)
    assert response.status_code == expected, response.text
    return response.json()


def send(client, path, body=None, expected=200, method="post"):
    response = getattr(client, method)("/api/v1" + path, json=body)
    assert response.status_code == expected, response.text
    return response.json()


@pytest.fixture
def school(clients):
    admin = clients["admin"]
    specialty = send(admin, "/specialties", {"name": "Інженерія ПЗ", "code": "ІПЗ"}, 201)
    subject = send(admin, "/subjects", {"name": "Операційні системи", "specialty_id": specialty["id"]}, 201)
    group = send(
        admin,
        "/student-groups",
        {"name": "ІПЗ-4", "specialty_id": specialty["id"], "academic_year": "2026/2027"},
        201,
    )
    course = send(
        admin,
        "/courses",
        {"subject_id": subject["id"], "name": "Операційні системи", "academic_year": "2026/2027"},
        201,
    )
    prefix = f"/courses/{course['id']}"
    send(admin, prefix + "/teachers", {"teacher_id": clients["teacher_id"]}, method="put")
    for key in ("student", "student2"):
        send(
            admin,
            prefix + "/memberships",
            {"student_id": clients[key + "_id"], "group_id": group["id"]},
            method="put",
        )
    return course
