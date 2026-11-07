import re
import unicodedata
from hashlib import sha256

APOSTROPHES = str.maketrans({"’": "'", "ʼ": "'", "‘": "'", "`": "'", "‐": "-", "‑": "-", "−": "-"})
NEGATIONS = frozenset({"не", "ні", "ані", "без", "немає", "жодний"})


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).translate(APOSTROPHES).split())


def canonical(text: str) -> str:
    return normalize(text).casefold()


def text_digest(text: str) -> str:
    return sha256(canonical(text).encode()).hexdigest()


def validate_text(text: str, minimum: int, maximum: int) -> str | None:
    normalized = normalize(text)
    if not minimum <= len(normalized) or len(text) > maximum or len(normalized) > maximum:
        return f"Відповідь має містити від {minimum} до {maximum} символів."
    if any(unicodedata.category(char).startswith("C") and char not in "\n\r\t" for char in text):
        return "Текст містить недопустимі керівні символи."
    if not any(char.isalpha() for char in normalized):
        return "Введіть текстову відповідь, що містить літери."
    symbols = sum(unicodedata.category(char)[0] in {"S", "P"} for char in normalized)
    if symbols / len(normalized) > 0.5:
        return "У відповіді забагато технічних символів."
    return None


def words_for_test(text: str) -> list[str]:
    return re.findall(r"[^\W_]+(?:'[^\W_]+)*", canonical(text))
