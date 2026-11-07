from uuid import uuid4

import pytest
from conftest import get, send
from sqlalchemy import select, text

from app.database.session import session
from app.models import Embedding, Submission
from app.nlp.provider import get_provider
from app.services.analysis_worker import claim_job, model_identity, process_one

pytestmark = pytest.mark.postgres
REFERENCE = "Операційна система керує обладнанням і забезпечує запуск програм."
CORRECT_VARIATION = "ОС управляє пристроями та дозволяє виконувати застосунки."
REJECTED_VARIATION = "Текстовий редактор малює зображення і друкує фотографії."


def question(teacher, course_id, status="published"):
    return send(
        teacher,
        "/questions",
        {
            "course_id": course_id,
            "text": "Для чого потрібна операційна система?",
            "status": status,
            "references": [
                {
                    "text": REFERENCE,
                    "concepts": [
                        {"concept": "обладнанням", "synonyms": ["пристроями"]},
                    ],
                }
            ],
        },
        201,
    )


def submit(student, question_id, answer, request_id=None):
    return send(
        student,
        "/submissions",
        {"question_id": question_id, "answer_text": answer, "request_id": str(request_id or uuid4())},
        201,
    )


def process():
    provider = get_provider()
    assert process_one(provider, model_identity(provider))


def test_roles_publication_ownership_and_visibility(clients, school):
    teacher, outsider, student, student2 = (
        clients[key] for key in ("teacher", "outsider", "student", "student2")
    )
    item = question(teacher, school["id"], "draft")
    path = f"/questions/{item['id']}"
    get(student, path, 404)
    get(outsider, path, 404)
    get(clients["anonymous"], path, 401)
    get(student, path + "/reference-answers", 403)
    send(teacher, path, {"status": "published"}, method="patch")
    assert "reference_count" not in get(student, path)
    send(teacher, f"/courses/{school['id']}", {"result_visibility": "reviewed"}, method="patch")
    value = "  " + REFERENCE + "\n"
    key = uuid4()
    answer = submit(student, item["id"], value, key)
    assert answer["status"] == "queued" and answer["answer_text"] == value
    assert get(student, "/submissions/summary") == {"completed_questions": 1, "pending_reviews": 1}
    assert get(student2, "/submissions/summary") == {"completed_questions": 0, "pending_reviews": 0}
    assert submit(student, item["id"], value, key)["id"] == answer["id"]
    path = f"/submissions/{answer['id']}"
    get(student2, path, 404)
    get(outsider, path, 404)
    get(student, path + "/history", 403)
    process()
    assert get(student, path + "/result")["analysis"] is None
    review_id = get(teacher, path + "/result")["analysis"]["id"]
    send(teacher, f"/reviews/{review_id}/approve", {"comment": "Зараховано."}, 201)
    result = get(student, path + "/result")
    assert set(result["analysis"]) == {"category", "final_similarity", "explanation"}
    assert result["review"]["decision"] == "approved"
    send(teacher, path + "/reanalyze", expected=202)
    process()
    assert get(student, path + "/result")["analysis"] is None
    assert get(student, path + "/result")["review"]["decision"] == "approved"
    send(teacher, f"/courses/{school['id']}", {"result_visibility": "hidden"}, method="patch")
    assert get(student, path + "/result")["review"] is None
    assert get(teacher, path + "/history")["total"] == 2


def test_review_variation_reused_only_while_approved(clients, school):
    teacher, student, student2 = (clients[key] for key in ("teacher", "student", "student2"))
    item = question(teacher, school["id"])
    reference_id = get(teacher, f"/questions/{item['id']}/reference-answers")[0]["id"]
    rejected = send(
        teacher, "/variations", {"reference_answer_id": reference_id, "text": REJECTED_VARIATION}, 201
    )
    send(teacher, f"/variations/{rejected['id']}/reject")
    invalid = submit(student, item["id"], REJECTED_VARIATION)
    process()
    result = get(teacher, f"/submissions/{invalid['id']}/result")
    assert result["analysis"]["variation_id"] is None
    first = submit(student, item["id"], CORRECT_VARIATION)
    process()
    endpoint = f"/submissions/{first['id']}"
    result = get(teacher, endpoint + "/result")
    assert result["analysis"]["variation_id"] is None
    review_id = result["analysis"]["id"]
    reviewed = send(
        teacher, f"/reviews/{review_id}/approve", {"save_variation": True, "comment": "Прийнято."}, 201
    )
    variation_id = reviewed["variation_id"]
    assert get(teacher, f"/variations/{variation_id}")["status"] == "approved"
    assert get(teacher, "/variations?status=approved")["total"] == 1
    assert get(teacher, "/reports/summary")["counts"]["reviewed"] == 1
    assert get(teacher, "/submissions?q=ОС%20управляє")["total"] == 1
    second = submit(student2, item["id"], CORRECT_VARIATION)
    process()
    second_path = f"/submissions/{second['id']}"
    analysis = get(teacher, second_path + "/result")["analysis"]
    assert analysis["variation_id"] == variation_id
    assert analysis["semantic_similarity"] == pytest.approx(1)
    send(teacher, f"/variations/{variation_id}/archive")
    send(teacher, second_path + "/reanalyze", expected=202)
    process()
    assert get(teacher, second_path + "/result")["analysis"]["variation_id"] is None
    assert get(teacher, second_path + "/history")["items"][1]["variation_id"] == variation_id
    with session() as db:
        assert len(db.scalars(select(Embedding)).all()) == 3
        assert (
            db.scalar(text("SELECT count(*) FROM pg_indexes WHERE indexname LIKE 'ix_embeddings_hnsw_%'"))
            == 2
        )


def test_nlp_failure_preserves_answer_and_supports_retry(clients, school, monkeypatch):
    teacher, student = clients["teacher"], clients["student"]
    item = question(teacher, school["id"])
    answer = submit(student, item["id"], REFERENCE)
    provider = get_provider()
    model = model_identity(provider)
    with monkeypatch.context() as context:

        def broken(_texts):
            raise RuntimeError("Fixture failure")

        context.setattr(provider, "encode", broken)
        assert process_one(provider, model)
    endpoint = f"/submissions/{answer['id']}"
    assert get(teacher, endpoint)["status"] == "failed"
    assert get(student, endpoint)["answer_text"] == REFERENCE
    send(teacher, endpoint + "/analyze", expected=202)
    assert process_one(provider, model)
    assert get(teacher, endpoint + "/result")["analysis"]["category"] == "HIGH_MATCH"


def test_queue_reclaims_expired_lease(clients, school):
    item = question(clients["teacher"], school["id"])
    answer = submit(clients["student"], item["id"], REFERENCE)
    job = claim_job()
    assert job.submission_id == answer["id"]
    assert claim_job() is None
    with session() as db, db.begin():
        db.execute(text("UPDATE submissions SET lease_until = NOW() - INTERVAL '1 second'"))
    process()
    with session() as db:
        assert db.get(Submission, answer["id"]).lease_token is None


def test_settings_crud_and_archive(clients, school):
    admin, teacher, student = (clients[key] for key in ("admin", "teacher", "student"))
    item = question(teacher, school["id"])
    path = f"/questions/{item['id']}"
    get(teacher, "/settings", 403)
    assert get(admin, "/settings")["calibrated"] is False
    send(admin, "/settings", {"high_threshold": 0.2}, 422, method="patch")
    send(admin, "/settings", {"max_answer_length": 55}, method="patch")
    assert get(student, path)["max_answer_length"] == 55
    send(student, "/submissions", {"question_id": item["id"], "answer_text": REFERENCE}, 422)
    send(student, "/submissions", {"question_id": item["id"], "answer_text": "!!!"}, 422)
    send(teacher, path + "/archive")
    get(student, path, 404)
    assert get(teacher, path)["status"] == "archived"
    assert get(admin, "/audit-log")["total"] > 0


def test_auth_refresh_logout_and_revocation(clients):
    client, admin = clients["student"], clients["admin"]
    assert get(client, "/auth/me")["role"] == "student"
    previous = client.cookies.get("empi_refresh")
    send(client, "/auth/refresh")
    assert client.cookies.get("empi_refresh") != previous
    send(admin, f"/users/{clients['student_id']}", {"active": False}, method="patch")
    get(client, "/auth/me", 401)
    send(client, "/auth/refresh", expected=401)
    send(admin, "/auth/logout")
    get(admin, "/auth/me", 401)
    assert clients["anonymous"].post("/api/v1/auth/login", headers={"X-EMPI-Request": ""}).status_code == 403
    for _ in range(10):
        send(clients["anonymous"], "/auth/login", {"email": "absent@example.org", "password": "invalid"}, 401)
    send(clients["anonymous"], "/auth/login", {"email": "absent@example.org", "password": "invalid"}, 429)
