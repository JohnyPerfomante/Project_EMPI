from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.api.common import Limit, Offset, Search, paginate, search_text
from app.core.errors import conflict, missing
from app.models import Course, CourseMembership, Role, Specialty, StudentGroup, Subject, TeacherCourse, User
from app.schemas.catalog import (
    CourseIn,
    CoursePatch,
    CourseView,
    GroupView,
    MembershipIn,
    MembershipView,
    SubjectView,
    TeacherAccessIn,
    TeacherAccessView,
)
from app.schemas.common import Page
from app.security.auth import DB, Actor, Admin, Staff
from app.services.access import course_scope, get_course
from app.services.audit import audit
from app.services.configuration import ANALYSIS_KEY, analysis_config, setting_row, validate_configuration

router = APIRouter(tags=["Навчальні дисципліни"])


@router.get("/subjects", response_model=Page[SubjectView])
def subjects(
    db: DB,
    actor: Actor,
    q: Search = None,
    specialty_id: int | None = None,
    offset: Offset = 0,
    limit: Limit = 25,
):
    query = select(Subject).order_by(Subject.name, Subject.id)
    if actor.role != Role.ADMIN:
        query = query.where(
            Subject.id.in_(
                select(Course.subject_id).where(
                    Course.id.in_(course_scope(actor, active_only=actor.role == Role.STUDENT))
                )
            )
        )
    if q:
        query = query.where(search_text(Subject.name, q))
    if specialty_id:
        query = query.where(Subject.specialty_id == specialty_id)
    return paginate(db, query, offset, limit)


def course_view(db, course, actor):
    subject = db.get(Subject, course.subject_id)
    return CourseView.model_validate(
        {
            **{
                key: getattr(course, key)
                for key in CourseView.model_fields
                if key not in ("subject_name", "specialty", "analysis_overrides")
            },
            "subject_name": subject.name,
            "specialty": db.get(Specialty, subject.specialty_id).code,
            "analysis_overrides": course.analysis_overrides if actor.role != Role.STUDENT else {},
        }
    )


@router.get("/courses", response_model=Page[CourseView])
def courses(
    db: DB,
    actor: Actor,
    q: Search = None,
    subject_id: int | None = None,
    active: bool | None = None,
    offset: Offset = 0,
    limit: Limit = 25,
):
    query = (
        select(Course)
        .join(Subject)
        .where(
            Course.id.in_(course_scope(actor, active_only=actor.role == Role.STUDENT)),
        )
        .order_by(Course.name, Course.id)
    )
    if q:
        query = query.where(search_text(Course.name, q) | search_text(Subject.name, q))
    if subject_id:
        query = query.where(Course.subject_id == subject_id)
    if active is not None:
        query = query.where(Course.active == active)
    return paginate(db, query, offset, limit, lambda course: course_view(db, course, actor))


@router.post("/courses", response_model=CourseView, status_code=201)
def create_course(body: CourseIn, db: DB, actor: Staff):
    if db.get(Subject, body.subject_id, with_for_update=True) is None:
        missing()
    if actor.role == Role.TEACHER and not db.scalar(
        select(Course.id)
        .where(
            Course.id.in_(course_scope(actor)),
            Course.subject_id == body.subject_id,
        )
        .limit(1)
    ):
        missing()
    course = Course(**body.model_dump())
    db.add(course)
    db.flush()
    if actor.role == Role.TEACHER:
        db.add(TeacherCourse(teacher_id=actor.id, course_id=course.id))
    audit(db, actor.id, "create", "course", course.id)
    db.commit()
    return course_view(db, course, actor)


@router.get("/courses/{course_id}", response_model=CourseView)
def course_details(course_id: int, db: DB, actor: Actor):
    return course_view(db, get_course(db, actor, course_id), actor)


@router.patch("/courses/{course_id}", response_model=CourseView)
def edit_course(course_id: int, body: CoursePatch, db: DB, actor: Staff):
    course = get_course(db, actor, course_id)
    setting_row(db, ANALYSIS_KEY, lock=True)
    db.refresh(course, with_for_update=True)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("academic_year", course.academic_year) != course.academic_year and db.scalar(
        select(CourseMembership.id).where(CourseMembership.course_id == course.id).limit(1)
    ):
        conflict("Рік курсу з історією зарахувань зафіксований.")
    if "analysis_overrides" in changes:
        validate_configuration(analysis_config(db).model_dump() | changes["analysis_overrides"])
    for key, value in changes.items():
        setattr(course, key, value)
    audit(db, actor.id, "update", "course", course.id, fields=sorted(changes))
    db.commit()
    return course_view(db, course, actor)


@router.get("/courses/{course_id}/groups", response_model=Page[GroupView])
def course_groups(course_id: int, db: DB, actor: Staff, offset: Offset = 0, limit: Limit = 25):
    course = get_course(db, actor, course_id)
    subject = db.get(Subject, course.subject_id)
    query = (
        select(StudentGroup)
        .where(
            StudentGroup.specialty_id == subject.specialty_id,
            StudentGroup.academic_year == course.academic_year,
        )
        .order_by(StudentGroup.name)
    )
    return paginate(db, query, offset, limit)


@router.get("/courses/{course_id}/memberships", response_model=Page[MembershipView])
def memberships(
    course_id: int, db: DB, actor: Staff, q: Search = None, offset: Offset = 0, limit: Limit = 25
):
    get_course(db, actor, course_id)
    query = (
        select(CourseMembership, User.full_name, StudentGroup.name)
        .join(
            User,
            User.id == CourseMembership.student_id,
        )
        .join(StudentGroup, StudentGroup.id == CourseMembership.group_id)
        .where(
            CourseMembership.course_id == course_id,
        )
        .order_by(User.full_name, CourseMembership.id)
    )
    if q:
        query = query.where(search_text(User.full_name, q) | search_text(StudentGroup.name, q))
    return paginate(db, query, offset, limit, lambda row: membership_view(*row), rows=True)


def membership_view(record, name, group):
    return MembershipView(
        id=record.id,
        created_at=record.created_at,
        student_id=record.student_id,
        group_id=record.group_id,
        full_name=name,
        group_name=group,
        active=record.active,
    )


@router.put("/courses/{course_id}/memberships", response_model=MembershipView)
def assign_student(course_id: int, body: MembershipIn, db: DB, actor: Staff):
    course = get_course(db, actor, course_id)
    db.refresh(course, with_for_update=True)
    student = db.get(User, body.student_id, with_for_update=True)
    group = db.get(StudentGroup, body.group_id, with_for_update=True)
    if not student or student.role != Role.STUDENT or not group or (body.active and not student.active):
        missing()
    if (
        group.specialty_id != db.get(Subject, course.subject_id).specialty_id
        or group.academic_year != course.academic_year
    ):
        conflict("Група має належати до спеціальності й навчального року курсу.")
    statement = insert(CourseMembership).values(course_id=course.id, **body.model_dump())
    record = db.scalar(
        statement.on_conflict_do_update(
            index_elements=["course_id", "student_id"],
            set_={"group_id": body.group_id, "active": body.active},
        ).returning(CourseMembership)
    )
    audit(db, actor.id, "set_membership", "course", course.id, student_id=student.id, active=record.active)
    db.commit()
    return membership_view(record, student.full_name, group.name)


@router.get("/courses/{course_id}/teachers", response_model=Page[TeacherAccessView])
def teachers(course_id: int, db: DB, actor: Admin, offset: Offset = 0, limit: Limit = 25):
    get_course(db, actor, course_id)
    query = (
        select(TeacherCourse, User.full_name)
        .join(User, User.id == TeacherCourse.teacher_id)
        .where(
            TeacherCourse.course_id == course_id,
        )
        .order_by(User.full_name, TeacherCourse.id)
    )
    return paginate(db, query, offset, limit, lambda row: teacher_view(*row), rows=True)


def teacher_view(record, name):
    return TeacherAccessView(
        id=record.id,
        created_at=record.created_at,
        teacher_id=record.teacher_id,
        full_name=name,
        active=record.active,
    )


@router.put("/courses/{course_id}/teachers", response_model=TeacherAccessView)
def assign_teacher(course_id: int, body: TeacherAccessIn, db: DB, actor: Admin):
    get_course(db, actor, course_id)
    teacher = db.get(User, body.teacher_id, with_for_update=True)
    if not teacher or teacher.role != Role.TEACHER or (body.active and not teacher.active):
        missing()
    statement = insert(TeacherCourse).values(course_id=course_id, **body.model_dump())
    record = db.scalar(
        statement.on_conflict_do_update(
            index_elements=["teacher_id", "course_id"],
            set_={"active": body.active},
        ).returning(TeacherCourse)
    )
    audit(
        db, actor.id, "set_teacher_access", "course", course_id, teacher_id=teacher.id, active=record.active
    )
    db.commit()
    return teacher_view(record, teacher.full_name)
