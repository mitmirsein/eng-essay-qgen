"""Deterministic pre-generation checks for source passages."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from .package_io import CANONICAL_GRADES, GRADE_ALIASES
from .text_metrics import count_words

SECTION_RE = re.compile(r"(?:^|\n)\(([A-Z])\)\s*", re.MULTILINE)
SENTENCE_RE = re.compile(r"[^.!?]+(?:[.!?]+|$)", re.MULTILINE)
WORD_RE = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*|\d+(?:[-/]\d+)*")
GRADE_SENTENCE_TARGETS = {
    "중1": 18,
    "중2": 22,
    "중3": 26,
    "고1": 32,
    "고2/3": 38,
}


def _normalize_grade(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = GRADE_ALIASES.get(value.strip(), value.strip())
    if normalized not in CANONICAL_GRADES:
        raise ValueError(f"unsupported grade: {value}")
    return normalized


def _sections(text: str) -> dict[str, str]:
    matches = list(SECTION_RE.finditer(text))
    return {
        match.group(1): text[
            match.end() : matches[index + 1].start() if index + 1 < len(matches) else None
        ].strip()
        for index, match in enumerate(matches)
    }


def _sentence_lengths(text: str) -> list[int]:
    return [
        len(WORD_RE.findall(sentence)) for sentence in SENTENCE_RE.findall(text) if sentence.strip()
    ]


def _abnormal_whitespace(text: str) -> list[str]:
    issues = []
    if "\t" in text:
        issues.append("tab character")
    if re.search(r"[ \t]+(?:\n|$)", text):
        issues.append("trailing whitespace")
    if re.search(r" {3,}", text):
        issues.append("three or more consecutive spaces")
    return issues


def _control_characters(text: str) -> list[str]:
    found = []
    for character in text:
        category = unicodedata.category(character)
        if category.startswith("C") and character not in {"\n", "\r", "\t"}:
            found.append(f"U+{ord(character):04X}")
    return sorted(set(found))


def validate_passage(
    text: str,
    *,
    grade: str | None = None,
    question_type: str = "type1",
    min_section_words: int = 10,
) -> dict[str, Any]:
    """Return deterministic passage metrics and gate results.

    This function does not claim semantic correctness. Style, factuality, bias, and evidence
    sufficiency remain semantic or human-review tasks.
    """

    if question_type not in {"type1", "type2", "type3"}:
        raise ValueError(f"unsupported question_type: {question_type}")
    normalized_grade = _normalize_grade(grade)
    sentences = _sentence_lengths(text)
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text.strip()) if item.strip()]
    sections = _sections(text)
    metrics = {
        "word_count": count_words(text),
        "paragraph_count": len(paragraphs),
        "sentence_count": len(sentences),
        "sentence_words": {
            "min": min(sentences) if sentences else 0,
            "max": max(sentences) if sentences else 0,
            "average": sum(sentences) / len(sentences) if sentences else 0.0,
        },
        "section_ids": sorted(sections),
        "section_word_counts": {key: count_words(value) for key, value in sorted(sections.items())},
        "abnormal_whitespace": _abnormal_whitespace(text),
        "control_characters": _control_characters(text),
    }
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not text.strip():
        errors.append({"code": "empty_passage", "message": "passage is empty"})
    if metrics["paragraph_count"] == 0:
        errors.append({"code": "no_paragraph", "message": "passage has no non-empty paragraph"})
    if metrics["abnormal_whitespace"]:
        errors.append(
            {
                "code": "abnormal_whitespace",
                "message": "passage contains abnormal whitespace",
                "details": metrics["abnormal_whitespace"],
            }
        )
    if metrics["control_characters"]:
        errors.append(
            {
                "code": "control_character",
                "message": "passage contains control or formatting characters",
                "details": metrics["control_characters"],
            }
        )
    if normalized_grade and sentences:
        target = GRADE_SENTENCE_TARGETS[normalized_grade]
        average = metrics["sentence_words"]["average"]
        if average > target:
            warnings.append(
                {
                    "code": "sentence_length_attention",
                    "message": (
                        f"average sentence length {average:.1f} exceeds the "
                        f"{normalized_grade} attention target {target}"
                    ),
                    "details": {"average": average, "target": target},
                }
            )
    if question_type == "type2":
        missing = [key for key in ("A", "B") if key not in sections]
        if missing:
            errors.append(
                {
                    "code": "type2_sections_missing",
                    "message": "type2 passage must contain sections A and B",
                    "details": {"missing": missing, "found": sorted(sections)},
                }
            )
        short = {
            key: words
            for key, words in metrics["section_word_counts"].items()
            if key in {"A", "B"} and words < min_section_words
        }
        if short:
            errors.append(
                {
                    "code": "type2_section_too_short",
                    "message": f"type2 sections must contain at least {min_section_words} words",
                    "details": short,
                }
            )

    checks = [
        {"id": "non_empty", "status": "pass" if text.strip() else "fail"},
        {
            "id": "whitespace_and_characters",
            "status": "pass"
            if not metrics["abnormal_whitespace"] and not metrics["control_characters"]
            else "fail",
        },
        {
            "id": "type2_sections",
            "status": "pass"
            if question_type != "type2"
            or (
                "A" in sections
                and "B" in sections
                and not any(
                    key in {"A", "B"} and value < min_section_words
                    for key, value in metrics["section_word_counts"].items()
                )
            )
            else "fail",
        },
    ]
    return {
        "ok": not errors,
        "grade": normalized_grade,
        "question_type": question_type,
        "metrics": metrics,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "semantic_review_required": True,
    }
