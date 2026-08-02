"""Deterministic assessment and student-render security validation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .package_io import normalize_assessment, schema_errors
from .text_metrics import (
    count_words,
    find_ngram_matches,
    has_placeholder,
    normalized_tokens,
    regex_count,
)

SUPPORTED_KINDS = {
    "word_count",
    "surface_pattern",
    "literal_required",
    "ngram_limit",
    "format",
    "semantic",
}
FORBIDDEN_STUDENT_TERMS = (
    "모범 답안",
    "Sample Answer",
    "채점 기준",
    "채점기준",
    "배점표",
    "Rubric",
)


@dataclass
class ValidationIssue:
    code: str
    message: str
    path: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.path:
            data["path"] = self.path
        if self.details:
            data["details"] = self.details
        return data


def _param(params: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in params:
            return params[name]
    return default


def _as_literals(params: dict[str, Any]) -> list[str]:
    values = _param(params, "values", "literals", "value", default=[])
    if isinstance(values, str):
        return [values]
    if isinstance(values, list):
        return [value for value in values if isinstance(value, str)]
    return []


def _condition_check(
    condition: dict[str, Any],
    answer: dict[str, Any],
    passage_text: str,
    literal_whitelist: list[str],
) -> tuple[dict[str, Any], list[ValidationIssue], list[ValidationIssue]]:
    validation = condition.get("validation") or {}
    kind = validation.get("kind")
    mode = validation.get("check_mode")
    params = validation.get("params") or {}
    condition_id = condition.get("id", "?")
    answer_id = answer.get("id", "?")
    answer_text = answer.get("text", "")
    result: dict[str, Any] = {
        "condition_id": condition_id,
        "answer_id": answer_id,
        "kind": kind,
        "check_mode": mode,
    }
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    if kind not in SUPPORTED_KINDS:
        errors.append(
            ValidationIssue(
                "unsupported_validation_kind",
                f"unsupported validation kind: {kind!r}",
                f"conditions[{condition_id}].validation.kind",
            )
        )
        result["status"] = "fail"
        return result, errors, warnings
    if mode in {"semantic", "manual"} or kind == "semantic":
        result["status"] = "deferred"
        warnings.append(
            ValidationIssue(
                "semantic_check_deferred",
                f"{condition_id} is {mode or 'semantic'} and requires meaning-based review",
                f"conditions[{condition_id}]",
            )
        )
        return result, errors, warnings

    result["status"] = "pass"
    if kind == "word_count":
        actual = count_words(answer_text)
        minimum = _param(params, "min", "minimum")
        maximum = _param(params, "max", "maximum")
        result["actual"] = actual
        result["min"] = minimum
        result["max"] = maximum
        if (
            not isinstance(minimum, int)
            or not isinstance(maximum, int)
            or minimum < 0
            or maximum < minimum
        ):
            errors.append(
                ValidationIssue(
                    "invalid_word_count_params",
                    f"word_count requires integer min <= max, got {minimum!r}, {maximum!r}",
                    f"conditions[{condition_id}].validation.params",
                )
            )
        elif not minimum <= actual <= maximum:
            result["status"] = "fail"
            errors.append(
                ValidationIssue(
                    "word_count_out_of_range",
                    f"answer {answer_id} has {actual} words; expected {minimum}~{maximum}",
                    f"answers[{answer_id}]",
                    {"actual": actual, "min": minimum, "max": maximum},
                )
            )
    elif kind == "surface_pattern":
        pattern = _param(params, "pattern", "regex")
        minimum = _param(params, "min_count", "min", default=1)
        flags = (
            re.IGNORECASE
            if str(_param(params, "flags", default="i")).lower() in {"i", "ignorecase"}
            else 0
        )
        actual = regex_count(answer_text, pattern, flags=flags) if isinstance(pattern, str) else 0
        result["actual"] = actual
        result["min"] = minimum
        if not isinstance(pattern, str) or not pattern:
            errors.append(
                ValidationIssue(
                    "invalid_surface_pattern",
                    "surface_pattern requires a non-empty regex pattern",
                    f"conditions[{condition_id}].validation.params",
                )
            )
        elif actual < minimum:
            result["status"] = "fail"
            errors.append(
                ValidationIssue(
                    "surface_pattern_missing",
                    f"answer {answer_id} has {actual} matches; expected at least {minimum}",
                    f"answers[{answer_id}]",
                    {"actual": actual, "min": minimum, "pattern": pattern},
                )
            )
    elif kind == "literal_required":
        required = _as_literals(params)
        case_sensitive = bool(_param(params, "case_sensitive", default=False))
        missing = []
        for literal in required:
            if not _contains_literal(answer_text, literal, case_sensitive=case_sensitive):
                missing.append(literal)
        result["required"] = required
        result["missing"] = missing
        if missing:
            result["status"] = "fail"
            errors.append(
                ValidationIssue(
                    "required_literal_missing",
                    f"answer {answer_id} is missing required text: {', '.join(missing)}",
                    f"answers[{answer_id}]",
                )
            )
    elif kind == "ngram_limit":
        n = _param(params, "n", "min_n", "length", default=5)
        try:
            n = int(n)
        except (TypeError, ValueError):
            n = 5
        matches = find_ngram_matches(
            passage_text,
            answer_text,
            n=n,
            whitelist=literal_whitelist + _as_literals(params),
        )
        result["n"] = n
        result["matches"] = matches
        if matches:
            result["status"] = "fail"
            errors.append(
                ValidationIssue(
                    "forbidden_ngram_copy",
                    f"answer {answer_id} copies {n}+ consecutive passage words",
                    f"answers[{answer_id}]",
                    {"matches": matches},
                )
            )
    elif kind == "format":
        starts_with = _param(params, "starts_with", "prefix")
        ends_with = _param(params, "ends_with", "suffix")
        normalized_answer = " ".join(normalized_tokens(answer_text))
        normalized_start = (
            " ".join(normalized_tokens(starts_with)) if isinstance(starts_with, str) else None
        )
        normalized_end = (
            " ".join(normalized_tokens(ends_with)) if isinstance(ends_with, str) else None
        )
        start_ok = normalized_start is None or normalized_answer.startswith(normalized_start)
        end_ok = normalized_end is None or normalized_answer.endswith(normalized_end)
        result.update(
            {
                "starts_with": starts_with,
                "ends_with": ends_with,
                "start_ok": start_ok,
                "end_ok": end_ok,
            }
        )
        if not start_ok or not end_ok:
            result["status"] = "fail"
            errors.append(
                ValidationIssue(
                    "format_requirement_failed",
                    f"answer {answer_id} does not satisfy the required start/end format",
                    f"answers[{answer_id}]",
                    {"starts_with": starts_with, "ends_with": ends_with},
                )
            )
    return result, errors, warnings


def _contains_literal(text: str, literal: str, *, case_sensitive: bool) -> bool:
    from .text_metrics import contains_literal

    return contains_literal(text, literal, case_sensitive=case_sensitive)


def _validate_differentiated(assessment: dict[str, Any]) -> dict[str, Any]:
    """Validate each differentiated level against its own conditions and rubric."""

    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    checks: list[dict[str, Any]] = []
    answer_reports: list[dict[str, Any]] = []
    levels = assessment.get("differentiated_levels", [])
    expected_total = float(assessment["metadata"]["total_points"])
    passage_text = assessment["passage"]["text"]
    seen_levels: set[str] = set()
    if not levels:
        errors.append(
            ValidationIssue(
                "missing_differentiated_levels", "differentiated assessment has no levels"
            )
        )

    for level in levels:
        level_id = level["id"]
        if level_id in seen_levels:
            errors.append(
                ValidationIssue(
                    "duplicate_level_id", f"duplicate differentiated level id: {level_id}"
                )
            )
        seen_levels.add(level_id)
        conditions = level["conditions"]
        rubric = level["rubric"]
        answers = level["model_answers"]
        condition_ids = [item["id"] for item in conditions]
        condition_set = set(condition_ids)
        linked: set[str] = set()
        points_total = 0.0
        if len(condition_ids) != len(condition_set):
            errors.append(
                ValidationIssue("duplicate_condition_id", f"duplicate condition id in {level_id}")
            )
        rubric_ids = [item["id"] for item in rubric]
        if len(rubric_ids) != len(set(rubric_ids)):
            errors.append(
                ValidationIssue("duplicate_rubric_id", f"duplicate rubric id in {level_id}")
            )
        answer_ids = [item["id"] for item in answers]
        if len(answer_ids) != len(set(answer_ids)):
            errors.append(
                ValidationIssue("duplicate_answer_id", f"duplicate answer id in {level_id}")
            )
        for item in rubric:
            points_total += float(item["points"])
            for condition_id in item["condition_ids"]:
                linked.add(condition_id)
                if condition_id not in condition_set:
                    errors.append(
                        ValidationIssue(
                            "rubric_condition_missing",
                            f"rubric {item['id']} in {level_id} references unknown "
                            f"condition {condition_id}",
                        )
                    )
        if abs(points_total - expected_total) > 1e-9:
            errors.append(
                ValidationIssue(
                    "rubric_total_mismatch",
                    f"{level_id} rubric total is {points_total:g}; expected {expected_total:g}",
                )
            )
        for condition_id in condition_set - linked:
            errors.append(
                ValidationIssue(
                    "condition_unlinked",
                    f"condition {condition_id} in {level_id} is not linked from any rubric item",
                )
            )
        checks.append(
            {
                "id": f"{level_id}.rubric_total",
                "status": "pass" if abs(points_total - expected_total) <= 1e-9 else "fail",
                "actual": points_total,
                "expected": expected_total,
            }
        )
        literal_whitelist: list[str] = []
        for condition in conditions:
            validation = condition.get("validation", {})
            if validation.get("kind") == "literal_required":
                literal_whitelist.extend(_as_literals(validation.get("params", {})))
        level_error_count_before = len(errors)
        for answer in answers:
            before_errors = len(errors)
            before_warnings = len(warnings)
            answer_report: dict[str, Any] = {
                "id": f"{level_id}/{answer['id']}",
                "level": answer["level"],
                "word_count": count_words(answer["text"]),
                "conditions": [],
            }
            if not answer["text"].strip():
                errors.append(
                    ValidationIssue(
                        "empty_model_answer", f"answer {level_id}/{answer['id']} is empty"
                    )
                )
            if has_placeholder(answer["text"]):
                errors.append(
                    ValidationIssue(
                        "placeholder_found",
                        f"answer {level_id}/{answer['id']} contains a placeholder",
                    )
                )
            for condition in conditions:
                result, condition_errors, condition_warnings = _condition_check(
                    condition, answer, passage_text, literal_whitelist
                )
                answer_report["conditions"].append(result)
                errors.extend(condition_errors)
                warnings.extend(condition_warnings)
            answer_report["error_count"] = len(errors) - before_errors
            answer_report["warning_count"] = len(warnings) - before_warnings
            answer_reports.append(answer_report)
        checks.append(
            {
                "id": f"{level_id}.model_answer_conditions",
                "status": "pass" if len(errors) == level_error_count_before else "fail",
                "answer_count": len(answers),
            }
        )

    return {
        "ok": not errors,
        "assessment_id": assessment["assessment_id"],
        "schema_version": assessment["schema_version"],
        "normalized_grade": assessment["metadata"]["grade"],
        "question_type": assessment["metadata"]["question_type"],
        "checks": checks,
        "errors": [item.as_dict() for item in errors],
        "warnings": [item.as_dict() for item in warnings],
        "answers": answer_reports,
    }


def validate_assessment(assessment: dict[str, Any]) -> dict[str, Any]:
    """Validate schema, package relationships, and all deterministic answer rules."""

    normalized = normalize_assessment(assessment)
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    checks: list[dict[str, Any]] = []
    schema = schema_errors(normalized)
    if schema:
        errors.extend(ValidationIssue("schema_invalid", item) for item in schema)
        return {
            "ok": False,
            "assessment_id": normalized.get("assessment_id"),
            "schema_version": normalized.get("schema_version"),
            "checks": checks,
            "errors": [item.as_dict() for item in errors],
            "warnings": [item.as_dict() for item in warnings],
            "answers": [],
        }

    metadata = normalized["metadata"]
    if metadata["question_type"] == "differentiated":
        return _validate_differentiated(normalized)
    conditions = normalized["conditions"]
    rubric = normalized["rubric"]
    answers = normalized["model_answers"]
    for collection_name, collection in (
        ("conditions", conditions),
        ("rubric", rubric),
        ("model_answers", answers),
    ):
        if not collection:
            errors.append(
                ValidationIssue(
                    "empty_required_collection",
                    f"{collection_name} must contain at least one item for a standard assessment",
                    collection_name,
                )
            )
    condition_ids = [item["id"] for item in conditions]
    rubric_ids = [item["id"] for item in rubric]
    answer_ids = [item["id"] for item in answers]

    for label, values, code in (
        ("condition", condition_ids, "duplicate_condition_id"),
        ("rubric", rubric_ids, "duplicate_rubric_id"),
        ("answer", answer_ids, "duplicate_answer_id"),
    ):
        seen: set[str] = set()
        for value in values:
            if value in seen:
                errors.append(ValidationIssue(code, f"duplicate {label} id: {value}"))
            seen.add(value)

    condition_set = set(condition_ids)
    linked: set[str] = set()
    points_total = 0.0
    for item in rubric:
        points_total += float(item["points"])
        for condition_id in item["condition_ids"]:
            if condition_id not in condition_set:
                errors.append(
                    ValidationIssue(
                        "rubric_condition_missing",
                        f"rubric {item['id']} references unknown condition {condition_id}",
                        f"rubric[{item['id']}]",
                    )
                )
            linked.add(condition_id)
    expected_total = float(metadata["total_points"])
    if abs(points_total - expected_total) > 1e-9:
        errors.append(
            ValidationIssue(
                "rubric_total_mismatch",
                f"rubric total is {points_total:g}; metadata total_points is {expected_total:g}",
                "rubric",
                {"rubric_total": points_total, "metadata_total": expected_total},
            )
        )
    for condition_id in condition_set - linked:
        errors.append(
            ValidationIssue(
                "condition_unlinked",
                f"condition {condition_id} is not linked from any rubric item",
                f"conditions[{condition_id}]",
            )
        )
    checks.append(
        {
            "id": "rubric_total",
            "status": "pass" if abs(points_total - expected_total) <= 1e-9 else "fail",
            "actual": points_total,
            "expected": expected_total,
        }
    )
    checks.append(
        {
            "id": "condition_rubric_links",
            "status": "pass" if not (condition_set - linked) else "fail",
        }
    )

    policy = normalized["language_policy"]
    if policy["max_language_penalty"] > expected_total:
        warnings.append(
            ValidationIssue(
                "language_penalty_exceeds_total",
                "max_language_penalty is greater than total_points",
                "language_policy.max_language_penalty",
            )
        )

    passage_text = normalized["passage"]["text"]
    literal_whitelist: list[str] = []
    for condition in conditions:
        validation = condition.get("validation", {})
        if validation.get("kind") == "literal_required":
            literal_whitelist.extend(_as_literals(validation.get("params", {})))

    answer_reports = []
    for answer in answers:
        answer_errors_before = len(errors)
        answer_warnings_before = len(warnings)
        answer_report: dict[str, Any] = {
            "id": answer["id"],
            "level": answer["level"],
            "word_count": count_words(answer["text"]),
            "conditions": [],
        }
        if not answer["text"].strip():
            errors.append(
                ValidationIssue(
                    "empty_model_answer",
                    f"answer {answer['id']} is empty",
                    f"model_answers[{answer['id']}].text",
                )
            )
        if has_placeholder(answer["text"]):
            errors.append(
                ValidationIssue(
                    "placeholder_found",
                    f"answer {answer['id']} contains a placeholder",
                    f"model_answers[{answer['id']}].text",
                )
            )
        for condition in conditions:
            result, condition_errors, condition_warnings = _condition_check(
                condition, answer, passage_text, literal_whitelist
            )
            answer_report["conditions"].append(result)
            errors.extend(condition_errors)
            warnings.extend(condition_warnings)
        answer_report["error_count"] = len(errors) - answer_errors_before
        answer_report["warning_count"] = len(warnings) - answer_warnings_before
        answer_reports.append(answer_report)

    checks.append(
        {
            "id": "model_answer_conditions",
            "status": "pass" if not errors else "fail",
            "answer_count": len(answers),
        }
    )
    if has_placeholder(passage_text) or has_placeholder(normalized["task"]["instruction_ko"]):
        errors.append(
            ValidationIssue(
                "placeholder_found", "passage or task contains an unresolved placeholder"
            )
        )

    return {
        "ok": not errors,
        "assessment_id": normalized["assessment_id"],
        "schema_version": normalized["schema_version"],
        "normalized_grade": metadata["grade"],
        "question_type": metadata["question_type"],
        "checks": checks,
        "errors": [item.as_dict() for item in errors],
        "warnings": [item.as_dict() for item in warnings],
        "answers": answer_reports,
        "rubric_total": points_total,
    }


def validate_student_security(
    student_text: str,
    *,
    model_answers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Scan a rendered student document without trusting its source context."""

    errors: list[ValidationIssue] = []
    for term in FORBIDDEN_STUDENT_TERMS:
        if term.casefold() in student_text.casefold():
            errors.append(
                ValidationIssue(
                    "forbidden_student_term", f"student output contains forbidden term: {term}"
                )
            )
    if has_placeholder(student_text):
        errors.append(
            ValidationIssue(
                "placeholder_found", "student output contains an unresolved placeholder"
            )
        )
    leaked_answers = []
    for answer in model_answers or []:
        text = answer.get("text", "")
        if len(normalized_tokens(text)) >= 6 and " ".join(normalized_tokens(text)) in " ".join(
            normalized_tokens(student_text)
        ):
            leaked_answers.append(answer.get("id"))
    if leaked_answers:
        errors.append(
            ValidationIssue(
                "model_answer_leak",
                "student output contains a model answer",
                details={"answer_ids": leaked_answers},
            )
        )
    return {
        "ok": not errors,
        "errors": [item.as_dict() for item in errors],
        "forbidden_terms": list(FORBIDDEN_STUDENT_TERMS),
    }
