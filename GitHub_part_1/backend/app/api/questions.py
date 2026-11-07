from typing import Literal

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.common import Limit, Offset, Search, paginate, search_text
from app.core.errors import conflict
from app.models import AnswerVariation, Course, Question, QuestionStatus, ReferenceAnswer, Role, Subject, User
from app.schemas.catalog import QuestionIn, QuestionPatch, QuestionView, ReferenceIn, ReferenceView
from app.schemas.common import Page
from app.security.auth import DB, Actor, Staff, now
from app.services.access import get_course, get_question, question_scope
from app.services.audit import audit
from app.services.configuration import analysis_config
from app.services.materials import concepts_for, reference_access, reference_view, save_reference

router = APIRouter(tags=["Банк питань"])


def base_question_query(actor):
    query = (
        question_scope(actor)
        .join(Course, Course.id == Question.course_id)
        .join(Subject, Subject.id == Course.subject_id)
        .add_columns(
            Course.name,
            Subject.name,
        )
    )
    if actor.role == Role.STUDENT:
        return query
    refs = select(func.count(ReferenceAnswer.id)).where(ReferenceAnswer.question_id == Question.id)
    variations = (
        select(func.count(AnswerVariation.id))
        .join(ReferenceAnswer, ReferenceAnswer.id == AnswerVariation.reference_answer_id)
        .where(
            ReferenceAnswer.question_id == Question.id,
        )
    )
    return query.join(User, User.id == Question.created_by).add_columns(
        User.full_name,
        refs.scalar_subquery(),
        variations.scalar_subquery(),
    )


def view_question(row, max_answer_length):
    question, course, subject, *private = row
    author, references, variations = private if private else (None, None, None)
    return QuestionView(
        id=question.id,
        created_at=question.created_at,
        updated_at=question.updated_at,
        course_id=question.course_id,
        course_name=course,
        subject_name=subject,
        text=question.text,
        status=question.status,
        difficulty=question.difficulty,
        answer_type=question.answer_type,
        demo=question.demo,
        author=author,
        reference_count=references,
        variation_count=variations,
        max_answer_length=max_answer_length,
    )


@router.get("/questions", response_model=Page[QuestionView], response_model_exclude_none=True)
def questions(
    db: DB,
    actor: Actor,
    q: Search = None,
    course_id: int | None = None,
    subject_id: int | None = None,
    status: QuestionStatus | None = None,
    sort: Literal["newest", "oldest", "text"] = "newest",
    offset: Offset = 0,
    limit: Limit = 25,
):
    query = base_question_query(actor)
    if q:
        query = query.where(search_text(Question.text, q))
    if course_id:
        query = query.where(Question.course_id == course_id)
    if subject_id:
        query = query.where(Course.subject_id == subject_id)
    if status:
        query = query.where(Question.status == status)
    ordering = {"newest": Question.created_at.desc(), "oldest": Question.created_at, "text": Question.text}
    max_length = analysis_config(db).max_answer_length
    return paginate(
        db,
        query.order_by(ordering[sort], Question.id.desc()),
        offset,
        limit,
        lambda row: view_question(row, max_length),
        rows=True,
    )


@router.post("/questions", response_model=QuestionView, status_code=201)
def create_question(body: QuestionIn, db: DB, actor: Staff):
    course = get_course(db, actor, body.course_id, active_only=True)
    question = Question(
        course_id=course.id,
        text=body.text,
        status=body.status,
        difficulty=body.difficulty,
        created_by=actor.id,
    )
    db.add(question)
    db.flush()
    for reference in body.references:
        save_reference(db, question.id, reference)
    audit(db, actor.id, "create", "question", question.id, status=body.status)
    db.commit()
    return question_details(question.id, db, actor)


@router.get("/questions/{question_id}", response_model=QuestionView, response_model_exclude_none=True)
def question_details(question_id: int, db: DB, actor: Actor):
    get_question(db, actor, question_id)
    row = db.execute(base_question_query(actor).where(Question.id == question_id)).one()
    return view_question(row, analysis_config(db).max_answer_length)


@router.patch("/questions/{question_id}", response_model=QuestionView)
def update_question(question_id: int, body: QuestionPatch, db: DB, actor: Staff):
    record = get_question(db, actor, question_id, lock=True)
    if record.status == QuestionStatus.ARCHIVED:
        conflict("Архівне питання доступне для перегляду.")
    if body.status == QuestionStatus.PUBLISHED:
        get_course(db, actor, record.course_id, active_only=True)
        if not db.scalar(select(ReferenceAnswer.id).where(ReferenceAnswer.question_id == record.id).limit(1)):
            conflict("Для публікації потрібна еталонна відповідь.")
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(record, key, value)
    audit(db, actor.id, "update", "question", record.id, fields=sorted(changes), status=record.status)
    db.commit()
    return question_details(record.id, db, actor)


@router.post("/questions/{question_id}/archive", response_model=QuestionView)
def archive_question(question_id: int, db: DB, actor: Staff):
    record = get_question(db, actor, question_id, lock=True)
    if record.status != QuestionStatus.ARCHIVED:
        record.status, record.archived_at = QuestionStatus.ARCHIVED, now()
        audit(db, actor.id, "archive", "question", record.id)
        db.commit()
    return question_details(record.id, db, actor)


@router.get("/questions/{question_id}/reference-answers", response_model=list[ReferenceView])
def list_references(question_id: int, db: DB, actor: Staff):
    get_question(db, actor, question_id)
    refs = list(
        db.scalars(
            select(ReferenceAnswer)
            .where(
                ReferenceAnswer.question_id == question_id,
            )
            .order_by(ReferenceAnswer.id)
        )
    )
    grouped = concepts_for(db, [ref.id for ref in refs])
    return [reference_view(ref, grouped[ref.id]) for ref in refs]


@router.post("/questions/{question_id}/reference-answers", response_model=ReferenceView, status_code=201)
def create_reference(question_id: int, body: ReferenceIn, db: DB, actor: Staff):
    question = get_question(db, actor, question_id, lock=True)
    if question.status == QuestionStatus.ARCHIVED:
        conflict("Еталони архівного питання доступні для перегляду.")
    count = db.scalar(
        select(func.count(ReferenceAnswer.id)).where(ReferenceAnswer.question_id == question_id)
    )
    if count >= 12:
        conflict("Питання може містити до 12 еталонних відповідей.")
    view = save_reference(db, question_id, body)
    audit(db, actor.id, "create", "reference_answer", view.id, question_id=question_id)
    db.commit()
    return view


@router.patch("/reference-answers/{reference_id}", response_model=ReferenceView)
def edit_reference(reference_id: int, body: ReferenceIn, db: DB, actor: Staff):
    reference, question = reference_access(db, actor, reference_id, lock=True)
    if question.status == QuestionStatus.ARCHIVED:
        conflict("Еталони архівного питання доступні для перегляду.")
    view = save_reference(db, question.id, body, reference)
    audit(db, actor.id, "update", "reference_answer", view.id, question_id=question.id)
    db.commit()
    return view
