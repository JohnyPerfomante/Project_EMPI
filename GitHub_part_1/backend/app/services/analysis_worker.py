import logging
from dataclasses import dataclass
from datetime import timedelta
from time import monotonic, sleep
from uuid import uuid4

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.database.session import session
from app.models import (
    AnalysisResult,
    AnswerVariation,
    Course,
    Embedding,
    EmbeddingJob,
    ModelVersion,
    Question,
    ReferenceAnswer,
    Submission,
    SubmissionStatus,
    SystemSetting,
    VariationStatus,
)
from app.nlp.analyzer import ALGORITHM_VERSION, Candidate, analyze
from app.nlp.provider import Provider, get_provider
from app.nlp.text import text_digest
from app.schemas.catalog import ConceptIn, ConflictRule
from app.security.auth import now
from app.services.configuration import WORKER_KEY, analysis_config
from app.services.materials import concepts_for

log = logging.getLogger("empi.worker")


@dataclass(frozen=True)
class Job:
    submission_id: int
    token: str


def claim_job() -> Job | None:
    with session() as db, db.begin():
        time = now()
        record = db.scalar(
            select(Submission)
            .where(
                or_(
                    Submission.status == SubmissionStatus.QUEUED,
                    and_(Submission.status == SubmissionStatus.PROCESSING, Submission.lease_until < time),
                )
            )
            .order_by(Submission.created_at, Submission.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if record is None:
            return None
        record.status = SubmissionStatus.PROCESSING
        record.lease_until = time + timedelta(seconds=settings().job_lease_seconds)
        record.lease_token = str(uuid4())
        return Job(record.id, record.lease_token)


def load_inputs(job):
    with session() as db, db.begin():
        db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        submission = db.get(Submission, job.submission_id)
        question = db.get(Question, submission.question_id)
        course = db.get(Course, question.course_id)
        refs = list(
            db.scalars(
                select(ReferenceAnswer)
                .where(
                    ReferenceAnswer.question_id == question.id,
                )
                .order_by(ReferenceAnswer.id)
            )
        )
        ids = [ref.id for ref in refs]
        concepts = concepts_for(db, ids)
        approved = {key: [] for key in ids}
        for variation in db.scalars(
            select(AnswerVariation)
            .where(
                AnswerVariation.reference_answer_id.in_(ids),
                AnswerVariation.status == VariationStatus.APPROVED,
            )
            .order_by(AnswerVariation.id)
        ):
            approved[variation.reference_answer_id].append(variation)
        candidates = []
        for ref in refs:
            forms = [ConceptIn.model_validate(concept, from_attributes=True) for concept in concepts[ref.id]]
            rules = [ConflictRule.model_validate(rule) for rule in ref.conflict_rules]
            candidates.append(Candidate(ref.id, ref.text, ref.text, forms, rules))
            candidates.extend(
                Candidate(ref.id, ref.text, item.text, forms, rules, item.id) for item in approved[ref.id]
            )
        return submission.answer_text, candidates, analysis_config(db, course)


def model_identity(provider: Provider) -> int:
    with session() as db, db.begin():
        db.execute(
            insert(ModelVersion)
            .values(
                model_name=provider.name,
                model_version=provider.revision,
                embedding_dimension=provider.dimension,
            )
            .on_conflict_do_nothing()
        )
        model = db.scalar(
            select(ModelVersion).where(
                ModelVersion.model_name == provider.name,
                ModelVersion.model_version == provider.revision,
            )
        )
        if model.embedding_dimension != provider.dimension:
            raise ValueError("An existing model version has a different vector dimension")
        return model.id


def cached_embeddings(model_id, texts, provider):
    digests = [text_digest(text) for text in texts]
    with session() as db:
        records = {
            row.text_digest: row
            for row in db.scalars(
                select(Embedding).where(
                    Embedding.model_version_id == model_id,
                    Embedding.text_digest.in_(digests),
                )
            )
        }
    new = {digest: text for digest, text in zip(digests, texts, strict=True) if digest not in records}
    if new:
        vectors = provider.encode(list(new.values()))
        with session() as db, db.begin():
            db.execute(
                insert(Embedding)
                .values(
                    [
                        {"model_version_id": model_id, "text_digest": digest, "embedding": vector}
                        for digest, vector in zip(new, vectors, strict=True)
                    ]
                )
                .on_conflict_do_nothing(index_elements=["model_version_id", "text_digest"])
            )
            records.update(
                {
                    row.text_digest: row
                    for row in db.scalars(
                        select(Embedding).where(
                            Embedding.model_version_id == model_id,
                            Embedding.text_digest.in_(new),
                        )
                    )
                }
            )
    return [records[digest] for digest in digests]


def exact_similarities(embedding, candidates):
    with session() as db:
        distances = dict(
            db.execute(
                select(
                    Embedding.id,
                    Embedding.embedding.cosine_distance(embedding.embedding),
                ).where(Embedding.id.in_([item.id for item in candidates]))
            ).all()
        )
    return [max(0.0, min(1.0, 1 - distances[item.id])) for item in candidates]


def finish(job, *, result=None):
    with session() as db, db.begin():
        record = db.get(Submission, job.submission_id, with_for_update=True)
        if record.lease_token != job.token:
            return False
        record.lease_token = record.lease_until = None
        if result is None:
            record.status = SubmissionStatus.FAILED
        else:
            db.add(result)
            record.status = SubmissionStatus.ANALYZED
        return True


def process_one(provider: Provider, model_id: int) -> bool:
    job = claim_job()
    if job is None:
        return False
    started = monotonic()
    try:
        text, candidates, configuration = load_inputs(job)
        embedding, *embeddings = cached_embeddings(
            model_id, [text, *(item.text for item in candidates)], provider
        )
        score = analyze(provider, text, candidates, exact_similarities(embedding, embeddings), configuration)
        item = score.candidate
        processing_ms = round((monotonic() - started) * 1000)
        result = AnalysisResult(
            submission_id=job.submission_id,
            embedding_id=embedding.id,
            model_version_id=model_id,
            reference_answer_id=item.reference_id,
            variation_id=item.variation_id,
            semantic_similarity=score.semantic_similarity,
            lexical_similarity=score.lexical_similarity,
            concept_coverage=score.concept_coverage,
            final_similarity=score.final_similarity,
            category=score.category,
            explanation=score.explanation,
            warnings=score.warnings,
            matches=score.matches,
            missing=score.missing,
            configuration_snapshot={
                **configuration.model_dump(),
                "algorithm_version": ALGORITHM_VERSION,
                "morphology": getattr(provider, "morphology_version", "custom"),
            },
            material_snapshot={
                "reference_text": item.reference_text,
                "variation_text": item.text if item.variation_id is not None else None,
                "concepts": [concept.model_dump() for concept in item.concepts],
                "conflict_rules": [rule.model_dump() for rule in item.rules],
            },
            processing_ms=processing_ms,
        )
        if finish(job, result=result):
            log.info(
                "analysis_complete",
                extra={"submission_id": job.submission_id, "processing_ms": processing_ms},
            )
    except Exception as error:
        log.error(
            "analysis_failed", extra={"submission_id": job.submission_id, "error_type": type(error).__name__}
        )
        finish(job)
    return True


def warm_material(provider: Provider, model_id: int) -> bool:
    with session() as db, db.begin():
        pending = db.scalar(
            select(EmbeddingJob)
            .where(EmbeddingJob.ready_at <= now())
            .order_by(EmbeddingJob.ready_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if pending is None:
            return False
        try:
            cached_embeddings(model_id, [pending.text], provider)
        except SQLAlchemyError:
            raise
        except Exception as error:
            log.error("embedding_precompute_failed", extra={"error_type": type(error).__name__})
            pending.ready_at = now() + timedelta(minutes=1)
        else:
            db.delete(pending)
        return True


def heartbeat(state, detail):
    with session() as db, db.begin():
        db.execute(
            insert(SystemSetting)
            .values(setting_key=WORKER_KEY, setting_value={"state": state, "detail": detail})
            .on_conflict_do_update(
                index_elements=[SystemSetting.setting_key],
                set_={"setting_value": {"state": state, "detail": detail}, "updated_at": now()},
            )
        )


def run():
    provider, model_id = None, None
    pulse = 0.0
    while True:
        try:
            if provider is None:
                heartbeat("starting", "Завантажуються локальні моделі.")
                try:
                    loaded = get_provider()
                    model_id = model_identity(loaded)
                    provider = loaded
                except SQLAlchemyError:
                    raise
                except Exception as error:
                    log.error("model_load_failed", extra={"error_type": type(error).__name__})
                    heartbeat(
                        "degraded", "Модель недоступна. Перевірте наявність ваг і налаштування воркера."
                    )
                    sleep(15)
                    continue
            if monotonic() >= pulse:
                heartbeat("ready", f"{provider.name} · {provider.dimension} вимірів")
                pulse = monotonic() + 15
            if not process_one(provider, model_id) and not warm_material(provider, model_id):
                sleep(0.5)
        except SQLAlchemyError as error:
            log.error("worker_database_unavailable", extra={"error_type": type(error).__name__})
            sleep(3)
