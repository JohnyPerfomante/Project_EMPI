"""Compute metrics on a labelled Ukrainian corpus with the real local NLP provider."""

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np
from pydantic import Field, ValidationError
from sklearn.metrics import classification_report, confusion_matrix

from app.core.config import settings
from app.models import Category
from app.nlp.analyzer import ALGORITHM_VERSION, Candidate, analyze, cosine
from app.nlp.provider import LocalProvider
from app.nlp.text import text_digest, validate_text
from app.schemas.analysis import AnalysisSettings
from app.schemas.catalog import ReferenceIn
from app.schemas.common import Input
from scripts.seed_demo import load_examples


class Case(Input):
    question_id: str
    answer: str
    expected: Category
    references: list[ReferenceIn] = Field(min_length=1)


LABELS = [Category.HIGH_MATCH, Category.NEEDS_REVIEW, Category.LOW_MATCH]


def demo_cases():
    cases = []
    for index, example in enumerate(load_examples(), 1):
        reference = ReferenceIn(text=example.reference, concepts=example.concepts)
        for expected, answer in zip(
            LABELS, (example.correct, example.partial, example.incorrect), strict=True
        ):
            cases.append(
                Case(question_id=str(index), answer=answer, expected=expected, references=[reference])
            )
    return cases


def run(cases, corpus_name, config):
    provider = LocalProvider(settings())
    cache = {}
    durations, expected, predicted, rows = [], [], [], []
    by_question = defaultdict(int)
    for case in cases:
        if error := validate_text(case.answer, config.min_answer_length, config.max_answer_length):
            raise ValueError(f"Corpus item {case.question_id}: {error}")
        candidates = [
            Candidate(i, reference.text, reference.text, reference.concepts, reference.conflict_rules)
            for i, reference in enumerate(case.references, 1)
        ]
        missing = {
            text_digest(candidate.text): candidate.text
            for candidate in candidates
            if text_digest(candidate.text) not in cache
        }
        if missing:
            cache.update(zip(missing, provider.encode(list(missing.values())), strict=True))
        vector_keys = [text_digest(candidate.text) for candidate in candidates]
        started = perf_counter()
        vector = provider.encode([case.answer])[0]
        outcome = analyze(
            provider, case.answer, candidates, [cosine(vector, cache[key]) for key in vector_keys], config
        )
        durations.append((perf_counter() - started) * 1000)
        expected.append(case.expected.value)
        predicted.append(outcome.category.value)
        by_question[case.question_id] += 1
        rows.append(
            {
                "question_id": case.question_id,
                "case": by_question[case.question_id],
                "expected": case.expected,
                "predicted": outcome.category,
                "score": round(outcome.final_similarity, 4),
                "warnings": [warning["code"] for warning in outcome.warnings],
            }
        )
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "corpus": corpus_name,
        "cases": len(cases),
        "questions": len(by_question),
        "model": provider.name,
        "revision": provider.revision,
        "morphology": provider.morphology_version,
        "algorithm": ALGORITHM_VERSION,
        "config": config.model_dump(),
        "labels": LABELS,
        "metrics": classification_report(
            expected, predicted, labels=LABELS, zero_division=0, output_dict=True
        ),
        "confusion_matrix": confusion_matrix(expected, predicted, labels=LABELS).tolist(),
        "latency_ms": {
            "scope": "Warm model and reference vectors, no DB or HTTP",
            "p50": round(float(np.percentile(durations, 50)), 1),
            "p95": round(float(np.percentile(durations, 95)), 1),
            "max": round(max(durations), 1),
        },
        "cases_by_question": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo", action="store_true", help="Developer-labelled diagnostic corpus")
    source.add_argument("--corpus", type=Path, help="Reviewed JSONL corpus")
    parser.add_argument(
        "--settings", type=Path, help="Optional JSON containing the fixed analysis parameters"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        cases = (
            demo_cases()
            if args.demo
            else [
                Case.model_validate_json(line)
                for line in args.corpus.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        )
        if not cases:
            raise ValueError("Corpus has no cases.")
        config = (
            AnalysisSettings.model_validate_json(args.settings.read_text())
            if args.settings
            else AnalysisSettings()
        )
        results = run(cases, "DEMO, developer-labelled" if args.demo else args.corpus.name, config)
    except (OSError, ValidationError, ValueError) as error:
        raise SystemExit(str(error)) from None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {key: results[key] for key in ("cases", "metrics", "latency_ms")}, ensure_ascii=False, indent=2
        )
    )


if __name__ == "__main__":
    main()
