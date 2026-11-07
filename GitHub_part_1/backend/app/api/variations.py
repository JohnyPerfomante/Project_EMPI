from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import aliased

from app.api.common import Limit, Offset, Search, paginate, search_text
from app.core.errors import conflict, missing
from app.models import (
    AnswerVariation,
    Course,
    Question,
    QuestionStatus,
    ReferenceAnswer,
    User,
    VariationStatus,
)
from app.schemas.catalog import VariationIn, VariationView
from app.schemas.common import Page
from app.security.auth import DB, Staff
from app.services.access import course_scope
from app.services.materials import add_variation, reference_access, transition_variation

router = APIRouter(prefix="/variations", tags=["Варіації"])
LOCAL_TZ = ZoneInfo("Europe/Kyiv")
ACTIONS = {
    "approve": VariationStatus.APPROVED,
    "reject": VariationStatus.REJECTED,
    "archive": VariationStatus.ARCHIVED,
    "reopen": VariationStatus.PROPOSED,
}


def time_filter(query, column, date_from, date_to):
    if date_from and date_to and date_from > date_to:
        conflict("Початкова дата має передувати кінцевій.")
    if date_from:
        query = query.where(column >= datetime.combine(date_from, time.min, LOCAL_TZ))
    if date_to:
        query = query.where(
            column < datetime.combine(date_to, time.max, LOCAL_TZ) + timedelta(microseconds=1)
            if date_to < date.max
            else column <= datetime.combine(date_to, time.max, LOCAL_TZ)
        )
    return query


def variation_query(actor):
    author, reviewer = aliased(User), aliased(User)
    return (
        select(
            AnswerVariation,
            Question.id,
            Question.text,
            ReferenceAnswer.text,
            Course.name,
            author.full_name,
            reviewer.full_name,
        )
        .join(ReferenceAnswer, ReferenceAnswer.id == AnswerVariation.reference_answer_id)
        .join(Question, Question.id == ReferenceAnswer.question_id)
        .join(Course, Course.id == Question.course_id)
        .join(
            author,
            author.id == AnswerVariation.created_by,
        )
        .outerjoin(reviewer, reviewer.id == AnswerVariation.reviewed_by)
        .where(
            Course.id.in_(course_scope(actor)),
        )
    )


def variation_view(row):
    variation, question_id, question_text, reference_text, course_name, author, reviewer = row
    return VariationView(
        id=variation.id,
        created_at=variation.created_at,
        text=variation.text,
        status=variation.status,
        reference_answer_id=variation.reference_answer_id,
        question_id=question_id,
        question_text=question_text,
        reference_text=reference_text,
        course_name=course_name,
        author=author,
        reviewer=reviewer,
        approved_at=variation.approved_at,
        rejected_at=variation.rejected_at,
        archived_at=variation.archived_at,
        demo=variation.demo,
    )


@router.get("", response_model=Page[VariationView])
def variations(
    db: DB,
    actor: Staff,
    q: Search = None,
    status: VariationStatus | None = None,
    course_id: int | None = None,
    subject_id: int | None = None,
    question_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    offset: Offset = 0,
    limit: Limit = 25,
):
    query = variation_query(actor)
    if q:
        query = query.where(search_text(AnswerVariation.text, q) | search_text(Question.text, q))
    if status:
        query = query.where(AnswerVariation.status == status)
    if course_id:
        query = query.where(Course.id == course_id)
    if subject_id:
        query = query.where(Course.subject_id == subject_id)
    if question_id:
        query = query.where(Question.id == question_id)
    query = time_filter(query, AnswerVariation.created_at, date_from, date_to)
    return paginate(db, query.order_by(AnswerVariation.id.desc()), offset, limit, variation_view, rows=True)


@router.get("/{variation_id}", response_model=VariationView)
def variation_details(variation_id: int, db: DB, actor: Staff):
    row = db.execute(variation_query(actor).where(AnswerVariation.id == variation_id)).one_or_none()
    if row is None:
        missing()
    return variation_view(row)


@router.post("", response_model=VariationView, status_code=201)
def propose_variation(body: VariationIn, db: DB, actor: Staff):
    reference, question = reference_access(db, actor, body.reference_answer_id, lock=True)
    if question.status == QuestionStatus.ARCHIVED:
        conflict("Питання архівовано.")
    record = add_variation(db, reference, body.text, actor.id)
    db.commit()
    return variation_details(record.id, db, actor)


@router.post("/{variation_id}/{action}", response_model=VariationView)
def update_variation(
    variation_id: int, action: Literal["approve", "reject", "archive", "reopen"], db: DB, actor: Staff
):
    record = db.get(AnswerVariation, variation_id)
    if record is None:
        missing()
    _, question = reference_access(db, actor, record.reference_answer_id, lock=True)
    if question.status == QuestionStatus.ARCHIVED and action != "archive":
        conflict("Питання архівовано.")
    db.refresh(record)
    transition_variation(db, record, ACTIONS[action], actor.id)
    db.commit()
    return variation_details(record.id, db, actor)
