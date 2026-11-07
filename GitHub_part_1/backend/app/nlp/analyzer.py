from dataclasses import dataclass

import numpy as np

from app.models import Category
from app.nlp.provider import Document, Provider
from app.nlp.text import NEGATIONS
from app.schemas.analysis import AnalysisSettings
from app.schemas.catalog import ConceptIn, ConflictRule

ALGORITHM_VERSION = "1.0.0"


@dataclass(frozen=True)
class Candidate:
    reference_id: int
    reference_text: str
    text: str
    concepts: list[ConceptIn]
    rules: list[ConflictRule]
    variation_id: int | None = None


@dataclass(frozen=True)
class Score:
    candidate: Candidate
    semantic_similarity: float
    lexical_similarity: float
    concept_coverage: float | None
    final_similarity: float
    category: Category
    explanation: str
    warnings: list[dict]
    matches: list[str]
    missing: list[str]


def lexical_sentences(doc: Document) -> list[tuple[str, ...]]:
    return [tuple(token.lemma for token in sentence if token.pos not in {"PUNCT", "SYM"}) for sentence in doc]


def lexical_set(doc: Document) -> set[str]:
    return {word for sentence in lexical_sentences(doc) for word in sentence}


def cosine(left, right) -> float:
    norm = np.linalg.norm(left) * np.linalg.norm(right)
    return float(np.clip(np.dot(left, right) / norm, 0, 1)) if norm else 0.0


def phrase_in(needle: tuple[str, ...], haystack: list[tuple[str, ...]]) -> bool:
    if not needle:
        return False
    return any(
        sentence[index : index + len(needle)] == needle
        for sentence in haystack
        for index in range(len(sentence) - len(needle) + 1)
    )


def phrase(provider: Provider, text: str) -> tuple[str, ...]:
    return tuple(word for sentence in lexical_sentences(provider.morphology(text)) for word in sentence)


def negation_signals(doc: Document) -> set[tuple[str, str]]:
    signals = set()
    for sentence in doc:
        for index, token in enumerate(sentence):
            negation = token.lemma if token.lemma in NEGATIONS else token.text
            has_negative_feature = "Polarity=Neg" in token.features
            if negation not in NEGATIONS and not has_negative_feature:
                continue
            following = sentence[index + 1 : index + 5]
            if negation == "не" and following and following[0].lemma in {"тільки", "лише"}:
                continue
            content = next(
                (word.lemma for word in following if word.pos in {"VERB", "AUX", "NOUN", "ADJ", "ADV", ""}),
                "",
            )
            signals.add((negation if negation in NEGATIONS else token.lemma, content))
    return signals


def classify(
    score: float, configuration: AnalysisSettings, *, missing_required: bool, critical: bool, negation: bool
) -> Category:
    if critical or score < configuration.low_threshold:
        return Category.LOW_MATCH
    if missing_required or negation or score < configuration.high_threshold:
        return Category.NEEDS_REVIEW
    return Category.HIGH_MATCH


def analyze(
    provider: Provider,
    answer: str,
    candidates: list[Candidate],
    similarities: list[float],
    configuration: AnalysisSettings,
) -> Score:
    if not candidates or len(candidates) != len(similarities):
        raise ValueError("Candidate texts and similarities must correspond")
    answer_doc = provider.morphology(answer)
    sentences = lexical_sentences(answer_doc)
    answer_terms = lexical_set(answer_doc)
    ranked = []
    for candidate, semantic in zip(candidates, similarities, strict=True):
        candidate_doc = provider.morphology(candidate.text)
        terms = lexical_set(candidate_doc)
        union = answer_terms | terms
        lexical = len(answer_terms & terms) / len(union) if union else 0.0
        ranked.append((semantic, lexical, candidate, candidate_doc))
    semantic, lexical, candidate, candidate_doc = max(ranked, key=lambda item: (item[0], item[1]))

    matches, missing, required_missing = [], [], []
    coverage_weight, total_weight = 0.0, 0.0
    for concept in candidate.concepts:
        total_weight += concept.importance_weight
        if any(phrase_in(phrase(provider, form), sentences) for form in (concept.concept, *concept.synonyms)):
            coverage_weight += concept.importance_weight
            matches.append(concept.concept)
        else:
            missing.append(concept.concept)
            if concept.is_required:
                required_missing.append(concept.concept)
    coverage = coverage_weight / total_weight if total_weight else None

    warnings = [
        {"code": rule.kind, "message": rule.message, "evidence": rule.phrase, "critical": True}
        for rule in candidate.rules
        if phrase_in(phrase(provider, rule.phrase), sentences)
    ]
    critical = bool(warnings)
    negation = configuration.detect_negation and bool(
        negation_signals(answer_doc) - negation_signals(candidate_doc)
    )
    if negation:
        warnings.append(
            {
                "code": "negation",
                "message": "Є заперечення, відмінне від формулювання з найвищою подібністю.",
                "critical": False,
            }
        )
    if required_missing:
        warnings.append(
            {
                "code": "required_concepts",
                "message": "У відповіді бракує обов’язкових понять.",
                "evidence": required_missing,
                "critical": False,
            }
        )

    score = semantic * configuration.semantic_weight + lexical * configuration.lexical_weight
    if coverage is None:
        score /= configuration.semantic_weight + configuration.lexical_weight
    else:
        score += coverage * configuration.concept_weight
    score = min(1.0, max(0.0, score))
    category = classify(
        score, configuration, missing_required=bool(required_missing), critical=critical, negation=negation
    )
    explanation = {
        Category.HIGH_MATCH: "Висока подібність до навчального еталона. Остаточне рішення ухвалює викладач.",
        Category.NEEDS_REVIEW: "Відповідь потребує ручної перевірки через подібність, повноту або змістові маркери.",
        Category.LOW_MATCH: "Зафіксовано низьку подібність або критичну змістову ознаку. Остаточне рішення ухвалює викладач.",
    }[category]
    return Score(
        candidate, semantic, lexical, coverage, score, category, explanation, warnings, matches, missing
    )
