from datetime import datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Role(StrEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class QuestionStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class VariationStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class SubmissionStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    ANALYZED = "analyzed"
    FAILED = "failed"


class Decision(StrEnum):
    APPROVED = "approved"
    PARTIAL = "partial"
    REJECTED = "rejected"


class Category(StrEnum):
    HIGH_MATCH = "HIGH_MATCH"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    LOW_MATCH = "LOW_MATCH"


def enum_type(cls):
    return Enum(
        cls,
        name=cls.__name__.lower(),
        native_enum=False,
        create_constraint=True,
        values_callable=lambda members: [member.value for member in members],
    )


def time_column(**kwargs):
    return mapped_column(DateTime(timezone=True), **kwargs)


class Base(DeclarativeBase):
    pass


class Record:
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = time_column(server_default=func.now())


class Updated:
    updated_at: Mapped[datetime] = time_column(server_default=func.now(), onupdate=func.now())


class User(Record, Updated, Base):
    __tablename__ = "users"
    full_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[Role] = mapped_column(enum_type(Role), index=True)
    active: Mapped[bool] = mapped_column(default=True)
    demo: Mapped[bool] = mapped_column(default=False)
    last_login_at: Mapped[datetime | None] = time_column()


class Specialty(Record, Base):
    __tablename__ = "specialties"
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(160))


class Subject(Record, Base):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("specialty_id", "name"),)
    name: Mapped[str] = mapped_column(String(160))
    specialty_id: Mapped[int] = mapped_column(ForeignKey("specialties.id"), index=True)
    description: Mapped[str] = mapped_column(Text, default="")


class Course(Record, Updated, Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("subject_id", "name", "academic_year"),
        CheckConstraint(
            "result_visibility IN ('automatic', 'reviewed', 'hidden')", name="course_result_visibility"
        ),
    )
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    academic_year: Mapped[str] = mapped_column(String(9))
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(default=True)
    result_visibility: Mapped[str] = mapped_column(String(20), default="automatic")
    analysis_overrides: Mapped[dict] = mapped_column(JSON, default=dict)
    demo: Mapped[bool] = mapped_column(default=False)


class StudentGroup(Record, Base):
    __tablename__ = "student_groups"
    __table_args__ = (UniqueConstraint("specialty_id", "name", "academic_year"),)
    name: Mapped[str] = mapped_column(String(80))
    specialty_id: Mapped[int] = mapped_column(ForeignKey("specialties.id"))
    academic_year: Mapped[str] = mapped_column(String(9))


class CourseMembership(Record, Base):
    __tablename__ = "course_memberships"
    __table_args__ = (UniqueConstraint("course_id", "student_id"),)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("student_groups.id"), index=True)
    active: Mapped[bool] = mapped_column(default=True)


class TeacherCourse(Record, Base):
    __tablename__ = "teacher_courses"
    __table_args__ = (UniqueConstraint("teacher_id", "course_id"),)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    active: Mapped[bool] = mapped_column(default=True)


class Question(Record, Updated, Base):
    __tablename__ = "questions"
    __table_args__ = (Index("ix_question_course_status", "course_id", "status"),)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    text: Mapped[str] = mapped_column(Text)
    answer_type: Mapped[str] = mapped_column(String(20), default="open_text")
    difficulty: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[QuestionStatus] = mapped_column(enum_type(QuestionStatus), default=QuestionStatus.DRAFT)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    archived_at: Mapped[datetime | None] = time_column()
    demo: Mapped[bool] = mapped_column(default=False)


class ReferenceAnswer(Record, Updated, Base):
    __tablename__ = "reference_answers"
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    conflict_rules: Mapped[list[dict]] = mapped_column(JSON, default=list)


class ReferenceConcept(Record, Base):
    __tablename__ = "reference_concepts"
    __table_args__ = (
        UniqueConstraint("reference_answer_id", "concept"),
        CheckConstraint("importance_weight > 0 AND importance_weight <= 10", name="concept_weight"),
    )
    reference_answer_id: Mapped[int] = mapped_column(ForeignKey("reference_answers.id", ondelete="CASCADE"))
    concept: Mapped[str] = mapped_column(String(180))
    synonyms: Mapped[list[str]] = mapped_column(JSON, default=list)
    importance_weight: Mapped[float] = mapped_column(Float, default=1)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)


class AnswerVariation(Record, Base):
    __tablename__ = "answer_variations"
    __table_args__ = (
        UniqueConstraint("reference_answer_id", "text_digest"),
        Index("ix_variation_reference_status", "reference_answer_id", "status"),
    )
    reference_answer_id: Mapped[int] = mapped_column(ForeignKey("reference_answers.id"))
    text: Mapped[str] = mapped_column(Text)
    text_digest: Mapped[str] = mapped_column(String(64))
    status: Mapped[VariationStatus] = mapped_column(
        enum_type(VariationStatus), default=VariationStatus.PROPOSED
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = time_column()
    rejected_at: Mapped[datetime | None] = time_column()
    archived_at: Mapped[datetime | None] = time_column()
    demo: Mapped[bool] = mapped_column(default=False)


class Submission(Record, Base):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("student_id", "request_id"),
        Index("ix_submission_queue", "status", "created_at"),
        Index("ix_submissions_time", text("created_at DESC")),
    )
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    membership_id: Mapped[int] = mapped_column(ForeignKey("course_memberships.id"))
    group_id: Mapped[int] = mapped_column(ForeignKey("student_groups.id"), index=True)
    question_text: Mapped[str] = mapped_column(Text)
    answer_text: Mapped[str] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(36))
    status: Mapped[SubmissionStatus] = mapped_column(
        enum_type(SubmissionStatus), default=SubmissionStatus.QUEUED
    )
    lease_until: Mapped[datetime | None] = time_column()
    lease_token: Mapped[str | None] = mapped_column(String(36))


class ModelVersion(Record, Base):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("model_name", "model_version"),)
    model_name: Mapped[str] = mapped_column(String(255))
    model_version: Mapped[str] = mapped_column(String(255))
    embedding_dimension: Mapped[int] = mapped_column(Integer)


class Embedding(Record, Base):
    __tablename__ = "embeddings"
    __table_args__ = (UniqueConstraint("model_version_id", "text_digest"),)
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"))
    text_digest: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[list[float]] = mapped_column(Vector())


class EmbeddingJob(Base):
    __tablename__ = "embedding_jobs"
    text_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    ready_at: Mapped[datetime] = time_column(server_default=func.now(), index=True)


class AnalysisResult(Record, Base):
    __tablename__ = "analysis_results"
    __table_args__ = (Index("ix_analysis_latest", "submission_id", text("id DESC")),)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), index=True)
    embedding_id: Mapped[int] = mapped_column(ForeignKey("embeddings.id"))
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"))
    reference_answer_id: Mapped[int] = mapped_column(ForeignKey("reference_answers.id"))
    variation_id: Mapped[int | None] = mapped_column(ForeignKey("answer_variations.id"))
    semantic_similarity: Mapped[float] = mapped_column(Float)
    lexical_similarity: Mapped[float] = mapped_column(Float)
    concept_coverage: Mapped[float | None] = mapped_column(Float)
    final_similarity: Mapped[float] = mapped_column(Float)
    category: Mapped[Category] = mapped_column(enum_type(Category), index=True)
    explanation: Mapped[str] = mapped_column(Text)
    warnings: Mapped[list[dict]] = mapped_column(JSON)
    matches: Mapped[list[str]] = mapped_column(JSON)
    missing: Mapped[list[str]] = mapped_column(JSON)
    configuration_snapshot: Mapped[dict] = mapped_column(JSON)
    material_snapshot: Mapped[dict] = mapped_column(JSON)
    processing_ms: Mapped[int] = mapped_column(Integer)


class TeacherReview(Record, Base):
    __tablename__ = "teacher_reviews"
    __table_args__ = (Index("ix_review_latest", "analysis_result_id", text("id DESC")),)
    analysis_result_id: Mapped[int] = mapped_column(ForeignKey("analysis_results.id"), index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[Decision] = mapped_column(enum_type(Decision))
    comment: Mapped[str] = mapped_column(Text, default="")
    variation_id: Mapped[int | None] = mapped_column(ForeignKey("answer_variations.id"))


class SystemSetting(Updated, Base):
    __tablename__ = "system_settings"
    setting_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    setting_value: Mapped[dict] = mapped_column(JSON)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class AuditLog(Record, Base):
    __tablename__ = "audit_log"
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(45))


class AuthSession(Record, Base):
    __tablename__ = "auth_sessions"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    refresh_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = time_column(index=True)
    revoked_at: Mapped[datetime | None] = time_column()
    remember: Mapped[bool] = mapped_column(default=False)


class LoginThrottle(Base):
    __tablename__ = "login_throttle"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer)
    window_start: Mapped[datetime] = time_column(index=True)
