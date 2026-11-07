from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, StringConstraints, model_validator

from app.models import Category, Decision, SubmissionStatus
from app.schemas.common import Description, Input, Patch, RecordView


class AnalysisSettings(Input):
    high_threshold: float = Field(0.79, ge=0.05, le=1)
    low_threshold: float = Field(0.39, ge=0, le=0.95)
    semantic_weight: float = Field(0.72, ge=0.1, le=1)
    lexical_weight: float = Field(0.08, ge=0, le=1)
    concept_weight: float = Field(0.20, ge=0, le=1)
    min_answer_length: int = Field(5, ge=1, le=300)
    max_answer_length: int = Field(1800, ge=50, le=4000)
    detect_negation: bool = True

    @model_validator(mode="after")
    def check_settings(self):
        if self.high_threshold <= self.low_threshold:
            raise ValueError("Високий поріг має перевищувати низький.")
        if abs(self.semantic_weight + self.lexical_weight + self.concept_weight - 1) > 1e-6:
            raise ValueError("Сума ваг має дорівнювати 1.")
        if self.min_answer_length > self.max_answer_length:
            raise ValueError("Мінімальна довжина має бути меншою за максимальну.")
        return self


class AnalysisSettingsPatch(Patch):
    high_threshold: float | None = None
    low_threshold: float | None = None
    semantic_weight: float | None = None
    lexical_weight: float | None = None
    concept_weight: float | None = None
    min_answer_length: int | None = None
    max_answer_length: int | None = None
    detect_negation: bool | None = None


class SettingsView(AnalysisSettings):
    calibrated: bool = False
    model_name: str
    model_revision: str
    provider: str


class SubmissionIn(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    question_id: PositiveInt
    answer_text: Annotated[str, StringConstraints(min_length=1, max_length=4000)]
    request_id: UUID | None = None


class SubmissionView(RecordView):
    question_id: int
    question_text: str
    course_id: int
    course_name: str
    student_name: str | None = None
    group_name: str | None = None
    answer_text: str
    status: SubmissionStatus
    category: Category | None = None
    decision: Decision | None = None


class StudentSummary(BaseModel):
    completed_questions: int
    pending_reviews: int


class ReviewIn(Input):
    comment: Description = ""
    save_variation: bool = False
    reference_answer_id: PositiveInt | None = None


class ReviewView(RecordView):
    analysis_result_id: int
    decision: Decision
    comment: str
    reviewer: str | None = None
    variation_id: int | None = None


class AnalysisView(RecordView):
    semantic_similarity: float
    lexical_similarity: float
    concept_coverage: float | None
    final_similarity: float
    category: Category
    explanation: str
    reference_answer_id: int
    variation_id: int | None
    warnings: list[dict]
    matches: list[str]
    missing: list[str]
    processing_ms: int
    model_name: str
    model_version: str
    configuration_snapshot: dict
    material_snapshot: dict


class StudentAnalysis(BaseModel):
    final_similarity: float
    category: Category
    explanation: str


class ResultView(BaseModel):
    status: SubmissionStatus
    visibility: Literal["automatic", "reviewed", "hidden", "staff"]
    review_status: Literal["pending", "reviewed"]
    analysis: AnalysisView | StudentAnalysis | None
    review: ReviewView | None


class ReportCount(BaseModel):
    courses: int
    subjects: int
    questions: int
    submissions: int
    pending_reviews: int
    reviewed: int
    proposed_variations: int


class ReportCategory(BaseModel):
    category: Category
    count: int


class ReportDay(BaseModel):
    date: str
    count: int


class ReportCourse(BaseModel):
    course_id: int
    name: str
    submissions: int
    reviewed: int


class ReportStudent(BaseModel):
    student_id: int
    name: str
    submissions: int


class ReportSummary(BaseModel):
    counts: ReportCount
    categories: list[ReportCategory]
    activity: list[ReportDay]
    courses: list[ReportCourse]
    students: list[ReportStudent]


class AuditView(RecordView):
    user_id: int | None
    action: str
    entity_type: str
    entity_id: int | None
    details: dict
    ip_address: str | None


class HealthView(BaseModel):
    status: str
    database: str


class WorkerView(BaseModel):
    state: str
    detail: str
    updated_at: datetime | None
