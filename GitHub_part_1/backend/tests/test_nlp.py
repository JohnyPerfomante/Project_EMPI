import os

import pytest

from app.core.config import Settings
from app.models import Category
from app.nlp.analyzer import Candidate, analyze, cosine
from app.nlp.provider import LocalProvider
from app.nlp.provider import TestProvider as FixtureProvider
from app.nlp.text import normalize, text_digest, validate_text
from app.schemas.analysis import AnalysisSettings
from app.schemas.catalog import ConceptIn, ConflictRule

REFERENCE = "система керує обладнанням та запускає програми"
CANDIDATE = Candidate(
    1,
    REFERENCE,
    REFERENCE,
    [
        ConceptIn(concept="обладнанням", synonyms=["пристроями"]),
        ConceptIn(concept="запускає програми", synonyms=["виконує застосунки"]),
    ],
    [
        ConflictRule(
            phrase="переглядає пошту", kind="terminology", message="Згадано функцію поштового клієнта."
        )
    ],
)


@pytest.mark.parametrize(
    ("answer", "expected", "warnings"),
    [
        (REFERENCE, Category.HIGH_MATCH, set()),
        ("обладнанням керує система та запускає програми", Category.HIGH_MATCH, set()),
        ("система керує пристроями та запускає програми", Category.HIGH_MATCH, set()),
        ("система виконує застосунки і керує пристроями", Category.HIGH_MATCH, set()),
        ("система керує обладнанням та запускає", Category.NEEDS_REVIEW, {"required_concepts"}),
        ("система не керує обладнанням та запускає програми", Category.NEEDS_REVIEW, {"negation"}),
        ("система не тільки керує обладнанням та запускає програми", Category.HIGH_MATCH, set()),
        (
            "система керує обладнанням та запускає програми і переглядає пошту",
            Category.LOW_MATCH,
            {"terminology"},
        ),
        ("морква росте на городі", Category.LOW_MATCH, {"required_concepts"}),
    ],
)
def test_classification_rules(answer, expected, warnings):
    provider = FixtureProvider()
    # Fixed semantic inputs isolate the scoring rules from the separate real-model smoke test.
    semantic = 0.98 if answer != "морква росте на городі" else 0.12
    score = analyze(provider, answer, [CANDIDATE], [semantic], AnalysisSettings())
    assert score.category == expected
    assert {warning["code"] for warning in score.warnings} == warnings


@pytest.mark.parametrize("answer", ["", "  ", "12345", "!!!!!a", "Україн\x00ський", "р" * 30])
def test_invalid_text(answer):
    assert validate_text(answer, 5, 25)


def test_normalization_keeps_negation_and_unifies_apostrophes():
    assert normalize("  Я\tне   працюю з комп’ютером.\n") == "Я не працюю з комп'ютером."
    assert text_digest("КОМП’ЮТЕР") == text_digest("комп'ютер")


@pytest.mark.real_model
@pytest.mark.skipif(os.getenv("RUN_REAL_NLP") != "1", reason="Set RUN_REAL_NLP=1 after downloading models")
def test_local_ukrainian_morphology_and_semantic_vectors():
    provider = LocalProvider(Settings(app_env="development", nlp_provider="local"))
    doc = provider.morphology("Програми працюють з комп’ютерами.")
    assert any(token.lemma == "комп'ютер" and token.pos == "NOUN" for sentence in doc for token in sentence)
    ref, paraphrase, unrelated = provider.encode(
        [
            "Операційна система керує апаратними ресурсами комп’ютера та надає засоби взаємодії.",
            "ОС керує обладнанням комп’ютера і дозволяє користувачу працювати з ним.",
            "Восени на городі дозрівають гарбузи.",
        ]
    )
    assert len(ref) == provider.dimension
    assert cosine(ref, paraphrase) > cosine(ref, unrelated) + 0.2
