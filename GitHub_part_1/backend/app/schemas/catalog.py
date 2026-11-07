from datetime import datetime
from typing import Annotated, Literal

from pydantic import EmailStr, Field, PositiveInt, StringConstraints, model_validator

from app.models import QuestionStatus, Role, VariationStatus
from app.schemas.common import Description, Input, MaterialText, Name, Patch, RecordView, ShortName, Year

Password = Annotated[str, StringConstraints(strip_whitespace=False, min_length=12, max_length=128)]
Difficulty = Literal["easy", "medium", "hard"]
Visibility = Literal["automatic", "reviewed", "hidden"]
Phrase = Annotated[str, StringConstraints(min_length=1, max_length=180)]


class LoginIn(Input):
    email: EmailStr
    password: Annotated[str, StringConstraints(strip_whitespace=False, min_length=1, max_length=128)]
    remember: bool = False


class RegisterIn(Input):
    full_name: Annotated[str, StringConstraints(min_length=2, max_length=160, pattern=r"^[^\x00-\x1f\x7f]+$")]
    email: EmailStr
    role: Literal["student", "teacher"]
    password: Password
    password_confirmation: Password

    @model_validator(mode="after")
    def matching_passwords(self):
        if self.password != self.password_confirmation:
            raise ValueError("Паролі мають збігатися.")
        return self


class UserView(RecordView):
    full_name: str
    email: EmailStr
    role: Role
    active: bool
    demo: bool
    last_login_at: datetime | None


class UserCreate(Input):
    full_name: Name
    email: EmailStr
    password: Password
    role: Role


class UserPatch(Patch):
    full_name: Name | None = None
    email: EmailStr | None = None
    password: Password | None = None
    active: bool | None = None


class RolePatch(Input):
    role: Role


class SpecialtyIn(Input):
    code: Annotated[str, StringConstraints(min_length=2, max_length=20)]
    name: Name


class SpecialtyView(RecordView, SpecialtyIn):
    pass


class SubjectIn(Input):
    name: Name
    specialty_id: PositiveInt
    description: Description = ""


class SubjectView(RecordView, SubjectIn):
    pass


class GroupIn(Input):
    name: ShortName
    specialty_id: PositiveInt
    academic_year: Year


class GroupView(RecordView, GroupIn):
    pass


class CourseIn(Input):
    subject_id: PositiveInt
    name: Name
    academic_year: Year
    description: Description = ""
    result_visibility: Visibility = "automatic"


class CoursePatch(Patch):
    name: Name | None = None
    academic_year: Year | None = None
    description: Description | None = None
    result_visibility: Visibility | None = None
    active: bool | None = None
    analysis_overrides: dict[Literal["high_threshold", "low_threshold"], float] | None = None


class CourseView(RecordView, CourseIn):
    subject_name: str
    specialty: str
    active: bool
    demo: bool
    analysis_overrides: dict[str, float] = Field(default_factory=dict)


class MembershipIn(Input):
    student_id: PositiveInt
    group_id: PositiveInt
    active: bool = True


class MembershipView(RecordView, MembershipIn):
    full_name: str
    group_name: str


class TeacherAccessIn(Input):
    teacher_id: PositiveInt
    active: bool = True


class TeacherAccessView(RecordView, TeacherAccessIn):
    full_name: str


class ConceptIn(Input):
    concept: Phrase
    synonyms: list[Phrase] = Field(default_factory=list, max_length=15)
    importance_weight: float = Field(1, gt=0, le=10)
    is_required: bool = True


class ConflictRule(Input):
    phrase: Phrase
    kind: Literal["contradiction", "terminology"] = "contradiction"
    message: Annotated[str, StringConstraints(min_length=3, max_length=300)]


class ReferenceIn(Input):
    text: MaterialText
    concepts: list[ConceptIn] = Field(default_factory=list, max_length=24)
    conflict_rules: list[ConflictRule] = Field(default_factory=list, max_length=16)

    @model_validator(mode="after")
    def unique_concepts(self):
        names = [concept.concept.casefold() for concept in self.concepts]
        if len(set(names)) != len(names):
            raise ValueError("Ключові поняття мають бути унікальними.")
        return self


class ReferenceView(RecordView, ReferenceIn):
    question_id: int
    updated_at: datetime


class QuestionIn(Input):
    course_id: PositiveInt
    text: MaterialText
    difficulty: Difficulty = "medium"
    status: Literal["draft", "published"] = "draft"
    references: list[ReferenceIn] = Field(min_length=1, max_length=12)


class QuestionPatch(Patch):
    text: MaterialText | None = None
    difficulty: Difficulty | None = None
    status: Literal["draft", "published"] | None = None


class QuestionView(RecordView):
    course_id: int
    course_name: str
    subject_name: str
    text: str
    answer_type: str
    difficulty: Difficulty
    status: QuestionStatus
    author: str | None = None
    reference_count: int | None = None
    variation_count: int | None = None
    updated_at: datetime
    demo: bool
    max_answer_length: int


class VariationIn(Input):
    reference_answer_id: PositiveInt
    text: MaterialText


class VariationView(RecordView, VariationIn):
    status: VariationStatus
    question_id: int
    question_text: str
    reference_text: str
    course_name: str
    author: str
    reviewer: str | None
    approved_at: datetime | None
    rejected_at: datetime | None
    archived_at: datetime | None
    demo: bool
