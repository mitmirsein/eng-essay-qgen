"""Small, deterministic text metrics used by assessment QA."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

# English answers are the primary target. Apostrophes inside a word and hyphenated
# compounds count as one token; punctuation around them does not count.
WORD_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?:[A-Za-z]+(?:['’][A-Za-z]+)*(?:-[A-Za-z0-9]+(?:['’][A-Za-z]+)*)*|[0-9]+(?:-[0-9]+)*)"
    r"(?![A-Za-z0-9])"
)


def tokenize(text: str) -> list[str]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return [match.group(0) for match in WORD_RE.finditer(text)]


def count_words(text: str) -> int:
    return len(tokenize(text))


def normalize_token(token: str) -> str:
    return token.replace("’", "'").lower()


def normalized_tokens(text: str) -> list[str]:
    return [normalize_token(token) for token in tokenize(text)]


def _phrase_tokens(value: str) -> list[str]:
    return normalized_tokens(value)


def contains_literal(text: str, literal: str, *, case_sensitive: bool = False) -> bool:
    if not isinstance(literal, str) or not literal.strip():
        return False
    if case_sensitive:
        compact_text = " ".join(text.split())
        compact_literal = " ".join(literal.split())
        return compact_literal in compact_text
    return _phrase_tokens(literal) == [] or _contains_token_sequence(
        normalized_tokens(text), _phrase_tokens(literal)
    )


def regex_count(text: str, pattern: str, *, flags: int = re.IGNORECASE) -> int:
    return len(re.findall(pattern, text, flags=flags))


def _contains_token_sequence(tokens: list[str], sequence: list[str]) -> bool:
    if not sequence or len(sequence) > len(tokens):
        return False
    width = len(sequence)
    return any(
        tokens[index : index + width] == sequence for index in range(len(tokens) - width + 1)
    )


def find_ngram_matches(
    source_text: str,
    answer_text: str,
    *,
    n: int = 5,
    whitelist: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Find answer n-grams that occur in the passage, with token positions."""

    if n < 1:
        raise ValueError("n must be positive")
    source = normalized_tokens(source_text)
    answer = normalized_tokens(answer_text)
    allowed = [_phrase_tokens(item) for item in whitelist if isinstance(item, str)]
    matches: list[dict[str, Any]] = []
    seen: set[tuple[int, tuple[str, ...]]] = set()
    if len(answer) < n:
        return matches
    for answer_start in range(len(answer) - n + 1):
        window = answer[answer_start : answer_start + n]
        if any(_contains_token_sequence(allowed_phrase, window) for allowed_phrase in allowed):
            continue
        for source_start in range(len(source) - n + 1):
            if source[source_start : source_start + n] != window:
                continue
            key = (source_start, tuple(window))
            if key in seen:
                continue
            seen.add(key)
            matches.append(
                {
                    "phrase": " ".join(window),
                    "source_start": source_start,
                    "source_end": source_start + n - 1,
                    "answer_start": answer_start,
                    "answer_end": answer_start + n - 1,
                }
            )
    return matches


def has_placeholder(text: str) -> bool:
    patterns = (
        r"\bTODO\b",
        r"\bTBD\b",
        r"\{\{[^{}]*\}\}",
        r"\{%[^%]*%\}",
        r"\[(?:PLACEHOLDER|INSERT|YOUR_[A-Z_]+)\]",
        r"<\s*(?:placeholder|insert)\s*>",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)
