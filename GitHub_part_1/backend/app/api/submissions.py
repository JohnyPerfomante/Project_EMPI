from datetime import date
from typing import Literal

from fastapi import APIRouter
from sqlalchemy import distinct, func, select, true
from sqlalchemy.dialects.postgresql import insert

from app.api.common import Limit, Offset, Search, paginate, search_text
from app.api.variations import time_filter
from app.core.errors import conflict, fail, missing
from app.models import (
    AnalysisResult,
    Category,
    Course,
    CourseMembership,
    Decision,
    ModelVersion,
    Question,
    QuestionStatus,
    Role,
    StudentGroup,
    Submission,
    SubmissionStatus,
    TeacherReview,
    User,
)
from app.nlp.text import validate_text
from app.schemas.analysis import (
    AnalysisView,
    ResultView,
    ReviewIn,
    ReviewView,
    StudentAnalysis,
    StudentSummary,
    SubmissionIn,
    SubmissionView,
)
from app.schemas.common import Page
from app.security.auth import DB, Actor, Staff
from app.services.access import get_question
from app.services.audit import audit
from app.services.configuration import analysis_config
from app.services.materials import add_variation, reference_access
from app.services.submissions import get_submission, latest_review, submission_rows, submission_view

router = APIRouter(tags=["Відповіді та перевірка"])


def filtered_submissions(
    db, actor, *, q, course_id, group_id, status, category, date_from, date_to, review_status, offset, limit
):
    query, analysis, review = submission_rows(actor)
    if q:
        match = search_text(Submission.question_text, q) | search_text(Submission.answer_text, q)
        if actor.role != Role.STUDENT:
            match |= search_text(User.full_name, q)
        query = query.where(match)
    if course_id:
        query = query.where(Course.id == course_id)
    if group_id and actor.role != Role.STUDENT:
        query = query.where(StudentGroup.id == group_id)
    if status:
        query = query.where(Submission.status == status)
    if category and actor.role != Role.STUDENT:
        query = query.where(analysis.c.category == category)
    if review_status == "pending":
        query = query.where(review.c.id.is_(None))
    if review_status == "reviewed":
        query = query.where(review.c.id.is_not(None))
    query = time_filter(query, Submission.created_at, date_from, date_to)
    return paginate(
        db,
        query.order_by(Submission.id.desc()),
        offset,
        limit,
        lambda row: submission_view(row, actor),
        rows=True,
    )


@router.get("/submissions", response_model=Page[SubmissionView])
def list_submissions(
    db: DB,
    actor: Actor,
    q: Search = None,
    course_id: int | None = None,
    group_id: int | None = None,
    status: SubmissionStatus | None = None,
    category: Category | None = None,
    review_status: Literal["pending", "reviewed"] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    offset: Offset = 0,
    limit: Limit = 25,
):
    return filtered_submissions(
        db,
        actor,
        q=q,
        course_id=course_id,
        group_id=group_id,
        status=status,
        category=category,
        review_status=review_status,
        date_from=date_from,
        date_to=date_to,
        offset=offset,
        limit=limit,
    )


@router.get("/reviews/pending", response_model=Page[SubmissionView])
def pending_reviews(
    db: DB, actor: Staff, course_id: int | None = None, offset: Offset = 0, limit: Limit = 25
):
    return filtered_submissions(
        db,
        actor,
        q=None,
        course_id=course_id,
        group_id=None,
        status=SubmissionStatus.ANALYZED,
        category=None,
        review_status="pending",
        date_from=None,
        date_to=None,
        offset=offset,
        limit=limit,
    )


@router.post("/submissions", response_model=SubmissionView, status_code=201)
def submit(body: SubmissionIn, db: DB, actor: Actor):
    if actor.role != Role.STUDENT:
        fail(403, "forbidden", "Відповіді надсилають студенти.")
    request_id = str(body.request_id) if body.request_id else None
    if request_id:
        existing = db.scalar(
            select(Submission).where(Submission.student_id == actor.id, Submission.request_id == request_id)
        )
        if existing:
            return same_submission(existing, body, db, actor)
    question = get_question(db, actor, body.question_id, lock=True)
    course = db.get(Course, question.course_id, with_for_update=True)
    membership = db.scalar(
        select(CourseMembership)
        .where(
            CourseMembership.course_id == course.id,
            CourseMembership.student_id == actor.id,
            CourseMembership.active.is_(True),
        )
        .with_for_update()
    )
    if not membership or not course.active or question.status != QuestionStatus.PUBLISHED:
        missing()
    config = analysis_config(db, course)
    if error := validate_text(body.answer_text, config.min_answer_length, config.max_answer_length):
        fail(422, "invalid_answer", error)
    statement = (
        insert(Submission)
        .values(
            question_id=question.id,
            question_text=question.text,
            student_id=actor.id,
            membership_id=membership.id,
            group_id=membership.group_id,
            answer_text=body.answer_text,
            request_id=request_id,
            status=SubmissionStatus.QUEUED,
        )
        .on_conflict_do_nothing(index_elements=["student_id", "request_id"])
        .returning(Submission)
    )
    record = db.scalar(statement)
    if record is None:
        record = db.scalar(
            select(Submission).where(Submission.student_id == actor.id, Submission.request_id == request_id)
        )
        return same_submission(record, body, db, actor)
    audit(db, actor.id, "submit", "submission", record.id, question_id=question.id)
    db.commit()
    return submission_details(record.id, db, actor)


def same_submission(record, body, db, actor):
    if record.question_id != body.question_id or record.answer_text != body.answer_text:
        conflict("Ключ повторного надсилання вже використано для іншої відповіді.")
    return submission_details(record.id, db, actor)


@router.get("/submissions/summary", response_model=StudentSummary)
def student_summary(db: DB, actor: Actor):
    if actor.role != Role.STUDENT:
        fail(403, "forbidden", "Це зведення доступне в кабінеті студента.")
    review = latest_review()
    completed, pending = db.execute(
        select(func.count(distinct(Submission.question_id)), func.count().filter(review.c.id.is_(None)))
        .select_from(Submission)
        .outerjoin(review, true())
        .where(Submission.student_id == actor.id)
    ).one()
    return StudentSummary(completed_questions=completed, pending_reviews=pending)


@router.get("/submissions/{submission_id}", response_model=SubmissionView)
def submission_details(submission_id: int, db: DB, actor: Actor):
    query, _, _ = submission_rows(actor)
    row = db.execute(query.where(Submission.id == submission_id)).one_or_none()
    if row is None:
        missing()
    return submission_view(row, actor)


def analysis_rows(submission_id):
    return (
        select(AnalysisResult, ModelVersion.model_name, ModelVersion.model_version)
        .join(ModelVersion, ModelVersion.id == AnalysisResult.model_version_id)
        .where(
            AnalysisResult.submission_id == submission_id,
        )
        .order_by(AnalysisResult.id.desc())
    )


def analysis_view(row):
    result, model_name, model_version = row
    return AnalysisView(
        **{
            key: getattr(result, key)
            for key in AnalysisView.model_fields
            if key not in {"model_name", "model_version"}
        },
        model_name=model_name,
        model_version=model_version,
    )


def review_rows(submission_id):
    return (
        select(TeacherReview, User.full_name)
        .join(AnalysisResult, AnalysisResult.id == TeacherReview.analysis_result_id)
        .join(User, User.id == TeacherReview.teacher_id)
        .where(AnalysisResult.submission_id == submission_id)
        .order_by(TeacherReview.id.desc())
    )


def review_view(row, staff=True):
    record, reviewer = row
    return ReviewView(
        id=record.id,
        created_at=record.created_at,
        analysis_result_id=record.analysis_result_id,
        decision=record.decision,
        comment=record.comment,
        reviewer=reviewer if staff else None,
        variation_id=record.variation_id if staff else None,
    )


@router.get("/submissions/{submission_id}/result", response_model=ResultView)
def result_details(submission_id: int, db: DB, actor: Actor):
    submission = get_submission(db, actor, submission_id)
    course = db.get(Course, db.get(Question, submission.question_id).course_id)
    staff = actor.role != Role.STUDENT
    latest = db.execute(analysis_rows(submission_id).limit(1)).one_or_none()
    review = db.execute(review_rows(submission_id).limit(1)).one_or_none()
    visibility = "staff" if staff else course.result_visibility
    analysis = None
    if latest and (
        staff
        or visibility == "automatic"
        or (visibility == "reviewed" and review and review[0].analysis_result_id == latest[0].id)
    ):
        analysis = (
            analysis_view(latest)
            if staff
            else StudentAnalysis.model_validate(latest[0], from_attributes=True)
        )
    return ResultView(
        status=submission.status,
        visibility=visibility,
        review_status="reviewed" if review else "pending",
        analysis=analysis,
        review=review_view(review, staff) if review and visibility != "hidden" else None,
    )


@router.get("/submissions/{submission_id}/history", response_model=Page[AnalysisView])
def analysis_history(submission_id: int, db: DB, actor: Staff, offset: Offset = 0, limit: Limit = 25):
    get_submission(db, actor, submission_id)
    return paginate(db, analysis_rows(submission_id), offset, limit, analysis_view, rows=True)


@router.get("/submissions/{submission_id}/reviews", response_model=Page[ReviewView])
def review_history(submission_id: int, db: DB, actor: Staff, offset: Offset = 0, limit: Limit = 25):
    get_submission(db, actor, submission_id)
    return paginate(db, review_rows(submission_id), offset, limit, review_view, rows=True)


def queue_analysis(submission_id, db, actor, *, repeat):
    record = get_submission(db, actor, submission_id, lock=True)
    if record.status not in {SubmissionStatus.PROCESSING, SubmissionStatus.QUEUED}:
        if not repeat and record.status == SubmissionStatus.ANALYZED:
            conflict("Для збереження нового результату запустіть повторний аналіз.")
        record.status = SubmissionStatus.QUEUED
        audit(db, actor.id, "reanalyze" if repeat else "analyze", "submission", record.id)
        db.commit()
    return submission_details(record.id, db, actor)


@router.post("/submissions/{submission_id}/analyze", response_model=SubmissionView, status_code=202)
def enqueue_analysis(submission_id: int, db: DB, actor: Staff):
    return queue_analysis(submission_id, db, actor, repeat=False)


@router.post("/submissions/{submission_id}/reanalyze", response_model=SubmissionView, status_code=202)
def repeat_analysis(submission_id: int, db: DB, actor: Staff):
    return queue_analysis(submission_id, db, actor, repeat=True)


@router.post("/reviews/{analysis_id}/{action}", response_model=ReviewView, status_code=201)
def make_review(
    analysis_id: int, action: Literal["approve", "reject", "partial"], body: ReviewIn, db: DB, actor: Staff
):
    analysis = db.get(AnalysisResult, analysis_id)
    if not analysis:
        missing()
    submission = get_submission(db, actor, analysis.submission_id, lock=True)
    latest_id = db.scalar(
        select(AnalysisResult.id)
        .where(
            AnalysisResult.submission_id == submission.id,
        )
        .order_by(AnalysisResult.id.desc())
        .limit(1)
    )
    if latest_id != analysis_id or submission.status != SubmissionStatus.ANALYZED:
        conflict("Оцінювати можна останній завершений аналіз. Оновіть сторінку.")
    decision = {"approve": Decision.APPROVED, "reject": Decision.REJECTED, "partial": Decision.PARTIAL}[
        action
    ]
    variation = None
    if body.save_variation:
        if decision != Decision.APPROVED:
            conflict("Варіацію можна зберегти лише для підтвердженої відповіді.")
        reference, question = reference_access(
            db, actor, body.reference_answer_id or analysis.reference_answer_id, lock=True
        )
        if question.id != submission.question_id or question.status == QuestionStatus.ARCHIVED:
            conflict("Варіація має належати до еталона цього неархівного питання.")
        variation = add_variation(db, reference, submission.answer_text, actor.id, approved=True)
    review = TeacherReview(
        analysis_result_id=analysis_id,
        teacher_id=actor.id,
        decision=decision,
        comment=body.comment,
        variation_id=variation.id if variation else None,
    )
    db.add(review)
    db.flush()
    audit(
        db,
        actor.id,
        "review",
        "submission",
        submission.id,
        decision=decision,
        analysis_id=analysis_id,
        review_id=review.id,
    )
    db.commit()
    return review_view((review, actor.full_name))
