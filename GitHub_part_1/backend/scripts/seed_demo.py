from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from app.core.config import ROOT, settings
from app.database.session import session
from app.models import (
    AnswerVariation,
    Course,
    CourseMembership,
    Question,
    QuestionStatus,
    ReferenceAnswer,
    Role,
    Specialty,
    StudentGroup,
    Subject,
    Submission,
    TeacherCourse,
    User,
)
from app.nlp.text import text_digest
from app.schemas.catalog import ConceptIn, ReferenceIn
from app.security.auth import now, password_hasher
from app.services.materials import save_reference

TOPICS = {
    "alg": "Алгоритми та структури даних",
    "oop": "Об’єктно-орієнтоване програмування",
    "db": "Бази даних",
    "os": "Операційні системи",
    "net": "Комп’ютерні мережі",
    "arch": "Архітектура комп’ютерів",
    "dev": "Технології розроблення ПЗ",
}
DEMO_DOMAIN = "demo.edu.ua"
YEAR = "2026/2027"


@dataclass(frozen=True)
class Example:
    topic: str
    question: str
    reference: str
    concepts: list[ConceptIn]
    correct: str
    partial: str
    incorrect: str


def load_examples(path: Path = ROOT / "database" / "seeds" / "questions.tsv") -> list[Example]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        topic, question, reference, terms, correct, partial, incorrect = line.split("|")
        concepts = []
        for term in terms.split(";"):
            concept, *synonyms = term.split("~")
            concepts.append(ConceptIn(concept=concept, synonyms=synonyms))
        records.append(Example(topic, question, reference, concepts, correct, partial, incorrect))
    return records


def get_or_create(db, model, values, **identity):
    record = db.scalar(select(model).filter_by(**identity))
    if record is None:
        record = model(**identity, **values)
        db.add(record)
        db.flush()
    return record


def main():
    config = settings()
    password = config.demo_password.get_secret_value()
    if config.app_env != "development" or len(password) < 12:
        raise SystemExit(
            "Demo seed requires APP_ENV=development and DEMO_PASSWORD of at least 12 characters."
        )
    hashed = password_hasher.hash(password)
    with session() as db, db.begin():
        users = {}
        for handle, name, role in (
            ("admin", "Олександр Коваль", Role.ADMIN),
            ("teacher", "Олена Мельник", Role.TEACHER),
            ("student", "Марія Бондар", Role.STUDENT),
            ("student2", "Андрій Лисенко", Role.STUDENT),
        ):
            users[handle] = get_or_create(
                db,
                User,
                dict(full_name=name, role=role, password_hash=hashed, demo=True),
                email=f"{handle}@{DEMO_DOMAIN}",
            )
            if not users[handle].demo:
                raise ValueError("Demo account address is already used by a regular account")
        engineering = get_or_create(db, Specialty, {"name": "Інженерія програмного забезпечення"}, code="ІПЗ")
        computers = get_or_create(db, Specialty, {"name": "Комп’ютерна інженерія"}, code="КН")
        courses = {}
        for topic, name in TOPICS.items():
            specialty = computers if topic in {"arch", "os", "net"} else engineering
            subject = get_or_create(
                db,
                Subject,
                {"description": "Демонстраційна навчальна дисципліна."},
                name=name,
                specialty_id=specialty.id,
            )
            course = get_or_create(
                db,
                Course,
                {"demo": True, "description": subject.description},
                name=name,
                subject_id=subject.id,
                academic_year=YEAR,
            )
            if not course.demo:
                raise ValueError("A regular course has the same identity as a demo course")
            group = get_or_create(
                db,
                StudentGroup,
                {},
                name=f"{specialty.code}-4",
                specialty_id=specialty.id,
                academic_year=YEAR,
            )
            get_or_create(db, TeacherCourse, {}, teacher_id=users["teacher"].id, course_id=course.id)
            members = [
                get_or_create(
                    db,
                    CourseMembership,
                    {"group_id": group.id},
                    student_id=users[key].id,
                    course_id=course.id,
                )
                for key in ("student", "student2")
            ]
            courses[topic] = course, members
        examples = load_examples()
        for index, example in enumerate(examples):
            course, members = courses[example.topic]
            question = get_or_create(
                db,
                Question,
                {"created_by": users["teacher"].id, "demo": True, "status": QuestionStatus.PUBLISHED},
                course_id=course.id,
                text=example.question,
            )
            reference = db.scalar(
                select(ReferenceAnswer)
                .where(ReferenceAnswer.question_id == question.id)
                .order_by(ReferenceAnswer.id)
                .limit(1)
            )
            if reference is None:
                view = save_reference(
                    db, question.id, ReferenceIn(text=example.reference, concepts=example.concepts)
                )
                reference = db.get(ReferenceAnswer, view.id)
            get_or_create(
                db,
                AnswerVariation,
                {"text": example.correct, "created_by": users["teacher"].id, "demo": True},
                reference_answer_id=reference.id,
                text_digest=text_digest(example.correct),
            )
            if index % 2 == 0:
                member = members[(index // 2) % 2]
                answer = (example.correct, example.partial, example.incorrect)[(index // 2) % 3]
                get_or_create(
                    db,
                    Submission,
                    {
                        "question_text": question.text,
                        "answer_text": answer,
                        "membership_id": member.id,
                        "group_id": member.group_id,
                        "created_at": now() - timedelta(days=(index * 3) % 27),
                    },
                    student_id=member.student_id,
                    question_id=question.id,
                    request_id=f"00000000-0000-4000-8000-{index:012d}",
                )
    print(f"DEMO: {len(examples)} questions, {len(TOPICS)} courses. Suggested variations await review.")


if __name__ == "__main__":
    main()
