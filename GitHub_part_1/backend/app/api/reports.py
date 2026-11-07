from datetime import date, timedelta

from fastapi import APIRouter
from sqlalchemy import Date, cast, distinct, func, select

from app.api.common import Limit, Offset
from app.api.submissions import filtered_submissions
from app.api.variations import LOCAL_TZ, time_filter
from app.models import AnswerVariation, Course, Question, ReferenceAnswer, Submission, User, VariationStatus
from app.schemas.analysis import ReportCourse, ReportSummary, SubmissionView
from app.schemas.common import Page
from app.security.auth import DB, Staff, now
from app.services.access import course_scope
from app.services.submissions import with_status

router = APIRouter(prefix="/reports", tags=["Звітність"])


def summarize(db, actor, course_id, date_from, date_to):
    scope = course_scope(actor)
    if course_id:
        scope = scope.where(Course.id == course_id)
    course_count, subject_count = db.execute(
        select(func.count(Course.id), func.count(distinct(Course.subject_id))).where(Course.id.in_(scope))
    ).one()
    question_count = db.scalar(select(func.count(Question.id)).where(Question.course_id.in_(scope)))
    proposed = db.scalar(
        select(func.count(AnswerVariation.id))
        .join(ReferenceAnswer)
        .join(Question)
        .where(
            Question.course_id.in_(scope),
            AnswerVariation.status == VariationStatus.PROPOSED,
        )
    )
    day = cast(func.timezone("Europe/Kyiv", Submission.created_at), Date)
    query = (
        select(
            Submission.id.label("id"),
            Course.id.label("course_id"),
            Course.name.label("course_name"),
            Submission.student_id,
            day.label("date"),
        )
        .join(Question, Question.id == Submission.question_id)
        .join(Course, Course.id == Question.course_id)
        .where(Course.id.in_(scope))
    )
    query, analysis, review = with_status(query)
    data = time_filter(
        query.add_columns(analysis.c.category, review.c.id.label("review_id")),
        Submission.created_at,
        date_from,
        date_to,
    ).cte("scoped_submissions")
    total, reviewed = db.execute(select(func.count(data.c.id), func.count(data.c.review_id))).one()
    categories = db.execute(
        select(data.c.category, func.count().label("count"))
        .where(
            data.c.category.is_not(None),
        )
        .group_by(data.c.category)
        .order_by(data.c.category)
    ).all()
    end = date_to or now().astimezone(LOCAL_TZ).date()
    start = max(date_from or date.min, end - timedelta(days=min(29, (end - date.min).days)))
    observed = dict(
        db.execute(
            select(data.c.date, func.count()).where(data.c.date.between(start, end)).group_by(data.c.date)
        ).all()
    )
    dates = [start + timedelta(days=offset) for offset in range(max(0, (end - start).days + 1))]
    courses = db.execute(
        select(
            Course.id.label("course_id"),
            Course.name,
            func.count(data.c.id).label("submissions"),
            func.count(data.c.review_id).label("reviewed"),
        )
        .outerjoin(data, data.c.course_id == Course.id)
        .where(Course.id.in_(scope))
        .group_by(Course.id)
        .order_by(func.count(data.c.id).desc(), Course.id)
        .limit(100)
    ).all()
    students = db.execute(
        select(User.id.label("student_id"), User.full_name.label("name"), func.count().label("submissions"))
        .join(data, data.c.student_id == User.id)
        .group_by(User.id)
        .order_by(func.count().desc(), User.id)
        .limit(10)
    ).all()
    return {
        "counts": {
            "courses": course_count,
            "subjects": subject_count,
            "questions": question_count,
            "submissions": total,
            "pending_reviews": total - reviewed,
            "reviewed": reviewed,
            "proposed_variations": proposed,
        },
        "categories": [row._asdict() for row in categories],
        "activity": [{"date": day.isoformat(), "count": observed.get(day, 0)} for day in dates],
        "courses": [row._asdict() for row in courses],
        "students": [row._asdict() for row in students],
    }


@router.get("/summary", response_model=ReportSummary)
def summary(
    db: DB,
    actor: Staff,
    course_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    return summarize(db, actor, course_id, date_from, date_to)


@router.get("/courses", response_model=list[ReportCourse])
def course_report(db: DB, actor: Staff, date_from: date | None = None, date_to: date | None = None):
    return summarize(db, actor, None, date_from, date_to)["courses"]


@router.get("/submissions", response_model=Page[SubmissionView])
def submission_report(
    db: DB,
    actor: Staff,
    course_id: int | None = None,
    group_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    offset: Offset = 0,
    limit: Limit = 25,
):
    return filtered_submissions(
        db,
        actor,
        q=None,
        course_id=course_id,
        group_id=group_id,
        status=None,
        category=None,
        review_status=None,
        date_from=date_from,
        date_to=date_to,
        offset=offset,
        limit=limit,
    )
