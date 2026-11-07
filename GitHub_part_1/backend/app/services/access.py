from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import missing
from app.models import Course, CourseMembership, Question, QuestionStatus, Role, TeacherCourse, User


def course_scope(user: User, *, active_only: bool = False):
    query = select(Course.id)
    if user.role == Role.TEACHER:
        query = query.join(TeacherCourse, TeacherCourse.course_id == Course.id).where(
            TeacherCourse.teacher_id == user.id,
            TeacherCourse.active.is_(True),
        )
    if user.role == Role.STUDENT:
        query = query.join(CourseMembership, CourseMembership.course_id == Course.id).where(
            CourseMembership.student_id == user.id,
            CourseMembership.active.is_(True),
        )
    return query.where(Course.active.is_(True)) if active_only else query


def get_course(db: Session, user: User, course_id: int, *, active_only: bool = False) -> Course:
    record = db.scalar(
        select(Course).where(
            Course.id == course_id,
            Course.id.in_(
                course_scope(
                    user,
                    active_only=active_only or user.role == Role.STUDENT,
                )
            ),
        )
    )
    if record is None:
        missing()
    return record


def question_scope(user: User):
    query = select(Question).where(
        Question.course_id.in_(course_scope(user, active_only=user.role == Role.STUDENT)),
    )
    if user.role == Role.STUDENT:
        query = query.where(Question.status == QuestionStatus.PUBLISHED)
    return query


def get_question(db: Session, user: User, question_id: int, *, lock: bool = False) -> Question:
    query = question_scope(user).where(Question.id == question_id)
    record = db.scalar(query.with_for_update() if lock else query)
    if record is None:
        missing()
    return record
