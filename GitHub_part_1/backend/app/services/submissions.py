from sqlalchemy import select, true

from app.core.errors import missing
from app.models import (
    AnalysisResult,
    Course,
    Question,
    Role,
    StudentGroup,
    Submission,
    TeacherReview,
    User,
)
from app.schemas.analysis import SubmissionView
from app.services.access import course_scope


def submission_query(actor):
    query = (
        select(Submission)
        .join(Question, Question.id == Submission.question_id)
        .join(Course, Course.id == Question.course_id)
    )
    if actor.role == Role.STUDENT:
        return query.where(Submission.student_id == actor.id)
    return query.where(Course.id.in_(course_scope(actor)))


def get_submission(db, actor, submission_id, *, lock=False):
    query = submission_query(actor).where(Submission.id == submission_id)
    record = db.scalar(query.with_for_update(of=Submission) if lock else query)
    if record is None:
        missing()
    return record


def latest_analysis():
    return (
        select(AnalysisResult.id, AnalysisResult.category)
        .where(
            AnalysisResult.submission_id == Submission.id,
        )
        .correlate(Submission)
        .order_by(AnalysisResult.id.desc())
        .limit(1)
        .lateral("latest_analysis")
    )


def latest_review():
    return (
        select(TeacherReview.id, TeacherReview.decision, TeacherReview.analysis_result_id)
        .join(AnalysisResult, AnalysisResult.id == TeacherReview.analysis_result_id)
        .where(
            AnalysisResult.submission_id == Submission.id,
        )
        .correlate(Submission)
        .order_by(TeacherReview.id.desc())
        .limit(1)
        .lateral("latest_review")
    )


def with_status(query):
    analysis, review = latest_analysis(), latest_review()
    return query.outerjoin(analysis, true()).outerjoin(review, true()), analysis, review


def submission_rows(actor):
    query, analysis, review = with_status(submission_query(actor))
    return (
        query.join(User, User.id == Submission.student_id)
        .join(
            StudentGroup,
            StudentGroup.id == Submission.group_id,
        )
        .add_columns(
            Course.id,
            Course.name,
            Course.result_visibility,
            User.full_name,
            StudentGroup.name,
            analysis.c.category,
            review.c.decision,
            analysis.c.id,
            review.c.analysis_result_id,
        ),
        analysis,
        review,
    )


def submission_view(row, actor):
    (
        record,
        course_id,
        course_name,
        visibility,
        student,
        group,
        category,
        decision,
        analysis_id,
        reviewed_id,
    ) = row
    staff = actor.role != Role.STUDENT
    visible = (
        staff
        or visibility == "automatic"
        or (visibility == "reviewed" and decision is not None and analysis_id == reviewed_id)
    )
    return SubmissionView(
        id=record.id,
        created_at=record.created_at,
        question_id=record.question_id,
        question_text=record.question_text,
        course_id=course_id,
        course_name=course_name,
        student_name=student if staff else None,
        group_name=group if staff else None,
        answer_text=record.answer_text,
        status=record.status,
        category=category if visible else None,
        decision=decision if staff or visibility != "hidden" else None,
    )
