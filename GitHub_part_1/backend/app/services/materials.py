from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import conflict, missing
from app.models import AnswerVariation, EmbeddingJob, ReferenceAnswer, ReferenceConcept, VariationStatus
from app.nlp.text import text_digest
from app.schemas.catalog import ReferenceIn, ReferenceView
from app.security.auth import now
from app.services.access import get_question
from app.services.audit import audit


def reference_access(db, actor, reference_id, *, lock=False):
    ref = db.get(ReferenceAnswer, reference_id)
    if ref is None:
        missing()
    question = get_question(db, actor, ref.question_id, lock=lock)
    if lock:
        db.refresh(ref)
    return ref, question


def reference_view(ref, concepts):
    return ReferenceView(
        id=ref.id,
        created_at=ref.created_at,
        updated_at=ref.updated_at,
        question_id=ref.question_id,
        text=ref.text,
        conflict_rules=ref.conflict_rules,
        concepts=[
            {
                key: getattr(concept, key)
                for key in (
                    "concept",
                    "synonyms",
                    "importance_weight",
                    "is_required",
                )
            }
            for concept in concepts
        ],
    )


def concepts_for(db: Session, reference_ids: list[int]):
    concepts = {reference_id: [] for reference_id in reference_ids}
    for row in db.scalars(
        select(ReferenceConcept)
        .where(
            ReferenceConcept.reference_answer_id.in_(
                reference_ids,
            )
        )
        .order_by(ReferenceConcept.id)
    ):
        concepts[row.reference_answer_id].append(row)
    return concepts


def schedule_embedding(db, text):
    db.execute(insert(EmbeddingJob).values(text_digest=text_digest(text), text=text).on_conflict_do_nothing())


def save_reference(db: Session, question_id: int, body: ReferenceIn, ref: ReferenceAnswer | None = None):
    if ref is None:
        ref = ReferenceAnswer(question_id=question_id, text=body.text)
        db.add(ref)
        db.flush()
    else:
        if ref.text != body.text and db.scalar(
            select(AnswerVariation.id)
            .where(
                AnswerVariation.reference_answer_id == ref.id,
                AnswerVariation.status == VariationStatus.APPROVED,
            )
            .limit(1)
        ):
            conflict("Перед зміною тексту еталона архівуйте його затверджені варіації.")
        db.execute(delete(ReferenceConcept).where(ReferenceConcept.reference_answer_id == ref.id))
        ref.text = body.text
        ref.updated_at = now()
    ref.conflict_rules = [rule.model_dump() for rule in body.conflict_rules]
    concepts = [
        ReferenceConcept(reference_answer_id=ref.id, **concept.model_dump()) for concept in body.concepts
    ]
    db.add_all(concepts)
    db.flush()
    schedule_embedding(db, ref.text)
    return reference_view(ref, concepts)


def add_variation(db, reference, text, actor_id, *, approved=False, demo=False):
    digest = text_digest(text)
    variation = db.scalar(
        select(AnswerVariation).where(
            AnswerVariation.reference_answer_id == reference.id,
            AnswerVariation.text_digest == digest,
        )
    )
    if variation:
        if approved and variation.status == VariationStatus.APPROVED:
            return variation
        if not approved or variation.status != VariationStatus.PROPOSED:
            conflict("Таке формулювання вже є в базі варіацій цього еталона.")
    else:
        variation = AnswerVariation(
            reference_answer_id=reference.id,
            text=text,
            text_digest=digest,
            status=VariationStatus.PROPOSED,
            created_by=actor_id,
            demo=demo,
        )
        db.add(variation)
        db.flush()
        audit(db, actor_id, "propose", "variation", variation.id, reference_id=reference.id)
    if approved:
        transition_variation(db, variation, VariationStatus.APPROVED, actor_id)
    return variation


TRANSITIONS = {
    VariationStatus.PROPOSED: {VariationStatus.APPROVED, VariationStatus.REJECTED, VariationStatus.ARCHIVED},
    VariationStatus.APPROVED: {VariationStatus.ARCHIVED},
    VariationStatus.REJECTED: {VariationStatus.ARCHIVED, VariationStatus.PROPOSED},
    VariationStatus.ARCHIVED: {VariationStatus.PROPOSED},
}


def transition_variation(db, variation, status, actor_id):
    if variation.status == status:
        return
    previous = variation.status
    if status not in TRANSITIONS[previous]:
        conflict("Ця зміна статусу варіації недоступна.")
    variation.status = status
    date = now()
    if status == VariationStatus.APPROVED:
        variation.approved_at, variation.reviewed_by = date, actor_id
        schedule_embedding(db, variation.text)
    elif status == VariationStatus.REJECTED:
        variation.rejected_at, variation.reviewed_by = date, actor_id
    elif status == VariationStatus.ARCHIVED:
        variation.archived_at = date
    audit(db, actor_id, "status_change", "variation", variation.id, old=previous, new=status)
