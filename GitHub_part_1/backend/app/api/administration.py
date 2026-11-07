from fastapi import APIRouter
from sqlalchemy import func, select, update

from app.api.common import Limit, Offset, Search, paginate, search_text
from app.core.config import settings
from app.core.errors import conflict, missing
from app.models import (
    AuditLog,
    AuthSession,
    Course,
    CourseMembership,
    Role,
    Specialty,
    StudentGroup,
    Subject,
    TeacherCourse,
    User,
)
from app.schemas.analysis import AnalysisSettingsPatch, AuditView, HealthView, SettingsView, WorkerView
from app.schemas.catalog import (
    GroupIn,
    GroupView,
    RolePatch,
    SpecialtyIn,
    SpecialtyView,
    SubjectIn,
    SubjectView,
    UserCreate,
    UserPatch,
    UserView,
)
from app.schemas.common import Page
from app.security.auth import DB, Admin, now, password_hasher, require_login
from app.services.audit import audit
from app.services.configuration import (
    ANALYSIS_KEY,
    WORKER_KEY,
    analysis_config,
    setting_row,
    validate_configuration,
)

router = APIRouter(tags=["Адміністрування"])


@router.get("/users", response_model=Page[UserView])
def users(
    db: DB,
    actor: Admin,
    q: Search = None,
    role: Role | None = None,
    active: bool | None = None,
    offset: Offset = 0,
    limit: Limit = 25,
):
    query = select(User).order_by(User.full_name, User.id)
    if q:
        query = query.where(search_text(User.full_name, q) | search_text(User.email, q))
    if role:
        query = query.where(User.role == role)
    if active is not None:
        query = query.where(User.active == active)
    return paginate(db, query, offset, limit)


@router.post("/users", response_model=UserView, status_code=201)
def create_user(body: UserCreate, db: DB, actor: Admin):
    values = body.model_dump(exclude={"password", "email"})
    user = User(**values, email=body.email.lower(), password_hash=password_hasher.hash(body.password))
    db.add(user)
    db.flush()
    audit(db, actor.id, "create", "user", user.id, role=user.role)
    db.commit()
    return user


def find_user(db, user_id, lock=False):
    user = db.get(User, user_id, with_for_update=lock)
    if not user:
        missing()
    return user


@router.get("/users/{user_id}", response_model=UserView)
def get_user(user_id: int, db: DB, actor: Admin):
    return find_user(db, user_id)


def admin_mutation_lock(db, actor):
    db.execute(select(func.pg_advisory_xact_lock(820143)))
    db.refresh(actor)
    if actor.role != Role.ADMIN or not actor.active:
        require_login()


def revoke_sessions(db, user_id):
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now())
    )


@router.patch("/users/{user_id}", response_model=UserView)
def edit_user(user_id: int, body: UserPatch, db: DB, actor: Admin):
    admin_mutation_lock(db, actor)
    user = find_user(db, user_id, True)
    values = body.model_dump(exclude_unset=True)
    if values.get("active") is False and user.id == actor.id:
        conflict("Власний обліковий запис не можна заблокувати.")
    if "email" in values:
        values["email"] = values["email"].lower()
    if password := values.pop("password", None):
        user.password_hash = password_hasher.hash(password)
    if password or values.get("active") is False:
        revoke_sessions(db, user.id)
    for key, value in values.items():
        setattr(user, key, value)
    audit(db, actor.id, "update", "user", user.id, fields=sorted(values), password_changed=bool(password))
    db.commit()
    return user


@router.patch("/users/{user_id}/role", response_model=UserView)
def change_role(user_id: int, body: RolePatch, db: DB, actor: Admin):
    admin_mutation_lock(db, actor)
    user = find_user(db, user_id, True)
    if user.role == body.role:
        return user
    if user.id == actor.id:
        conflict("Власну роль адміністратора не можна змінити.")
    if user.role == Role.TEACHER:
        db.execute(update(TeacherCourse).where(TeacherCourse.teacher_id == user.id).values(active=False))
    if user.role == Role.STUDENT:
        db.execute(
            update(CourseMembership).where(CourseMembership.student_id == user.id).values(active=False)
        )
    audit(db, actor.id, "role_change", "user", user.id, old=user.role, new=body.role)
    user.role = body.role
    revoke_sessions(db, user.id)
    db.commit()
    return user


def catalog_write(db, actor, table, body, entity, record_id=None):
    record = db.get(table, record_id) if record_id else table()
    if record is None:
        missing()
    for key, value in body.model_dump().items():
        setattr(record, key, value)
    db.add(record)
    db.flush()
    audit(db, actor.id, "update" if record_id else "create", entity, record.id)
    db.commit()
    return record


@router.get("/specialties", response_model=Page[SpecialtyView])
def specialties(db: DB, actor: Admin, offset: Offset = 0, limit: Limit = 25):
    return paginate(db, select(Specialty).order_by(Specialty.code), offset, limit)


@router.post("/specialties", response_model=SpecialtyView, status_code=201)
def create_specialty(body: SpecialtyIn, db: DB, actor: Admin):
    return catalog_write(db, actor, Specialty, body, "specialty")


@router.put("/specialties/{record_id}", response_model=SpecialtyView)
def edit_specialty(record_id: int, body: SpecialtyIn, db: DB, actor: Admin):
    return catalog_write(db, actor, Specialty, body, "specialty", record_id)


@router.get("/student-groups", response_model=Page[GroupView])
def groups(db: DB, actor: Admin, offset: Offset = 0, limit: Limit = 25):
    return paginate(db, select(StudentGroup).order_by(StudentGroup.name), offset, limit)


@router.post("/student-groups", response_model=GroupView, status_code=201)
def create_group(body: GroupIn, db: DB, actor: Admin):
    return catalog_write(db, actor, StudentGroup, body, "student_group")


@router.put("/student-groups/{record_id}", response_model=GroupView)
def edit_group(record_id: int, body: GroupIn, db: DB, actor: Admin):
    group = db.get(StudentGroup, record_id, with_for_update=True)
    if not group:
        missing()
    if (group.specialty_id != body.specialty_id or group.academic_year != body.academic_year) and db.scalar(
        select(CourseMembership.id).where(CourseMembership.group_id == group.id).limit(1)
    ):
        conflict("Спеціальність і рік групи з історією зарахувань зафіксовані.")
    return catalog_write(db, actor, StudentGroup, body, "student_group", record_id)


@router.post("/subjects", response_model=SubjectView, status_code=201)
def create_subject(body: SubjectIn, db: DB, actor: Admin):
    return catalog_write(db, actor, Subject, body, "subject")


@router.put("/subjects/{record_id}", response_model=SubjectView)
def edit_subject(record_id: int, body: SubjectIn, db: DB, actor: Admin):
    subject = db.get(Subject, record_id, with_for_update=True)
    if not subject:
        missing()
    if subject.specialty_id != body.specialty_id and db.scalar(
        select(Course.id).where(Course.subject_id == record_id).limit(1)
    ):
        conflict("Спеціальність дисципліни з наявними курсами зафіксована.")
    return catalog_write(db, actor, Subject, body, "subject", record_id)


@router.get("/settings", response_model=SettingsView)
def get_settings(db: DB, actor: Admin):
    return settings_response(analysis_config(db))


def settings_response(configuration):
    config = settings()
    return {
        **configuration.model_dump(),
        "model_name": config.nlp_model,
        "model_revision": config.nlp_revision,
        "provider": config.nlp_provider,
        "calibrated": False,
    }


@router.patch("/settings", response_model=SettingsView)
def update_settings(body: AnalysisSettingsPatch, db: DB, actor: Admin):
    row = setting_row(db, ANALYSIS_KEY, lock=True)
    configuration = validate_configuration(row.setting_value | body.model_dump(exclude_unset=True))
    values = configuration.model_dump()
    for course in db.scalars(select(Course)):
        if course.analysis_overrides:
            validate_configuration(values | course.analysis_overrides)
    row.setting_value, row.updated_by = values, actor.id
    audit(db, actor.id, "update", "settings", None, fields=sorted(body.model_fields_set))
    db.commit()
    return settings_response(configuration)


@router.get("/audit-log", response_model=Page[AuditView])
def audit_log(db: DB, actor: Admin, q: Search = None, offset: Offset = 0, limit: Limit = 25):
    query = select(AuditLog).order_by(AuditLog.id.desc())
    if q:
        query = query.where(search_text(AuditLog.action, q) | search_text(AuditLog.entity_type, q))
    return paginate(db, query, offset, limit)


@router.get("/health", response_model=HealthView, tags=["Система"])
def health(db: DB):
    db.execute(select(1))
    return {"status": "ok", "database": "available"}


@router.get("/health/worker", response_model=WorkerView)
def worker_status(db: DB, actor: Admin):
    row = setting_row(db, WORKER_KEY)
    if row is None:
        return {"state": "offline", "detail": "Воркер ще не запущено.", "updated_at": None}
    state = row.setting_value["state"]
    detail = row.setting_value["detail"]
    if (now() - row.updated_at).total_seconds() > settings().job_lease_seconds * 2:
        state, detail = "offline", "Немає свіжого сигналу від воркера."
    return {"state": state, "detail": detail, "updated_at": row.updated_at}
