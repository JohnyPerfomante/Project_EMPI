from dataclasses import dataclass
from functools import lru_cache
from hashlib import blake2b
from importlib.metadata import version
from typing import Protocol

import numpy as np

from app.core.config import Settings, settings
from app.nlp.text import canonical, words_for_test


@dataclass(frozen=True)
class Token:
    text: str
    lemma: str
    pos: str = ""
    features: str = ""


Document = tuple[tuple[Token, ...], ...]
PROCESSORS = "tokenize,mwt,pos,lemma"


class Provider(Protocol):
    name: str
    revision: str
    dimension: int

    def morphology(self, text: str) -> Document: ...
    def encode(self, texts: list[str]) -> list[list[float]]: ...


class LocalProvider:
    def __init__(self, config: Settings):
        import stanza
        import torch
        from sentence_transformers import SentenceTransformer

        self.name = config.nlp_model
        self.revision = config.nlp_revision
        self.morphology_version = f"Stanza {version('stanza')} · uk/{PROCESSORS}"
        torch.set_num_threads(config.nlp_threads)
        self.pipeline = stanza.Pipeline(
            lang="uk",
            processors=PROCESSORS,
            dir=config.stanza_dir or stanza.resources.common.DEFAULT_MODEL_DIR,
            download_method=None,
            use_gpu=False,
            verbose=False,
        )
        self.model = SentenceTransformer(
            config.nlp_model,
            revision=config.nlp_revision or None,
            device=config.nlp_device,
            local_files_only=config.nlp_offline,
            trust_remote_code=False,
            model_kwargs={"use_safetensors": True},
        )
        self.dimension = self.model.get_embedding_dimension()
        if not self.dimension:
            raise ValueError("Embedding dimension is unavailable")
        revision = self.model[0].auto_model.config._commit_hash
        self.revision = revision or self.revision or "local-unversioned"
        self.morphology("Операційна система керує ресурсами.")
        self.encode(["Операційна система керує ресурсами."])

    @lru_cache(maxsize=512)
    def morphology(self, text: str) -> Document:
        doc = self.pipeline(canonical(text))
        return tuple(
            tuple(
                Token(word.text, canonical(word.lemma or word.text), word.upos or "", word.feats or "")
                for word in sentence.words
            )
            for sentence in doc.sentences
        )

    def encode(self, texts: list[str]) -> list[list[float]]:
        chunks = []
        spans = []
        max_tokens = max(16, self.model.max_seq_length - 4)
        for text in texts:
            text = canonical(text)
            offsets = self.model.tokenizer(
                text,
                add_special_tokens=False,
                return_offsets_mapping=True,
                verbose=False,
            )["offset_mapping"]
            start = len(chunks)
            for index in range(0, len(offsets), max_tokens):
                last = min(index + max_tokens, len(offsets))
                chunks.append(text[offsets[index][0] : offsets[last - 1][1]])
            if start == len(chunks):
                chunks.append(text)
            spans.append((start, len(chunks)))
        vectors = self.model.encode(
            chunks, batch_size=16, normalize_embeddings=True, show_progress_bar=False, convert_to_numpy=True
        )
        return [self.pool(vectors[start:end]) for start, end in spans]

    @staticmethod
    def pool(vectors):
        pooled = vectors.mean(axis=0)
        norm = np.linalg.norm(pooled)
        return (pooled / norm if norm else pooled).tolist()


class TestProvider:
    """Deterministic fixture for workflow tests. Configuration forbids its use outside APP_ENV=test."""

    name = "test/hash-vocabulary"
    revision = "1"
    dimension = 96
    morphology_version = "test/simple-tokenizer"

    def morphology(self, text: str) -> Document:
        return (tuple(Token(word, word) for word in words_for_test(text)),)

    def encode(self, texts: list[str]) -> list[list[float]]:
        result = []
        for text in texts:
            vector = [0.0] * self.dimension
            for token in words_for_test(text):
                index = (
                    int.from_bytes(blake2b(token.encode(), digest_size=4).digest(), "big") % self.dimension
                )
                vector[index] += 1
            result.append(vector)
        return result


@lru_cache
def get_provider() -> Provider:
    return TestProvider() if settings().nlp_provider == "test" else LocalProvider(settings())
