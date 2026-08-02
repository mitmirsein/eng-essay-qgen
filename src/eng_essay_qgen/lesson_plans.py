"""Schema and quality validation for lesson-plan.json."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .package_io import PROJECT_ROOT, normalize_assessment
from .text_metrics import has_placeholder
from .validators import validate_assessment

LESSON_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "lesson-plan.schema.json"
CURRICULUM_PATH = PROJECT_ROOT / "references" / "curriculum-2022.json"
EMOJI_RE = re.compile(r"[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]")


def _schema_errors(plan: dict[str, Any]) -> list[str]:
    schema = json.loads(LESSON_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(plan), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.path) or "$"
        errors.append(f"{location}: {error.message}")
    return errors


def load_curriculum_reference(path: str | Path = CURRICULUM_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_lesson_plan(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    return json.loads(source.read_text(encoding="utf-8"))


def _all_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _all_strings(child)]
    if isinstance(value, list):
        return [item for child in value for item in _all_strings(child)]
    return []


def _assessment_condition_ids(assessment: dict[str, Any]) -> set[str]:
    ids = {item["id"] for item in assessment.get("conditions", [])}
    for level in assessment.get("differentiated_levels", []):
        ids.update(f"{level['id']}.{item['id']}" for item in level.get("conditions", []))
    return ids


def _assessment_answer_ids(assessment: dict[str, Any]) -> set[str]:
    ids = {item["id"] for item in assessment.get("model_answers", [])}
    for level in assessment.get("differentiated_levels", []):
        ids.update(f"{level['id']}/{item['id']}" for item in level.get("model_answers", []))
    return ids


def validate_lesson_plan(
    plan: dict[str, Any],
    *,
    assessment: dict[str, Any] | None = None,
    curriculum_reference: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate structure plus cross-document and pedagogical invariants."""

    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    schema_errors = _schema_errors(plan)
    if schema_errors:
        return {
            "ok": False,
            "assessment_id": plan.get("assessment_id"),
            "errors": [{"code": "schema_invalid", "message": item} for item in schema_errors],
            "warnings": [],
            "checks": [],
        }

    sequence = plan["sequence"]
    duration = plan["overview"]["duration_minutes"]
    minutes_total = sum(item["minutes"] for item in sequence)
    if minutes_total != duration:
        errors.append(
            {
                "code": "duration_mismatch",
                "message": f"sequence totals {minutes_total} minutes; overview requires {duration}",
            }
        )
    for index, item in enumerate(sequence):
        if len(item["expected_responses"]) < len(item["questions"]):
            errors.append(
                {
                    "code": "question_response_mismatch",
                    "message": f"sequence[{index}] does not provide an expected response "
                    "for every question",
                }
            )
        if len(item["checks_for_understanding"]) < len(item["questions"]):
            errors.append(
                {
                    "code": "question_check_mismatch",
                    "message": f"sequence[{index}] does not provide a check for every question",
                }
            )

    reference = curriculum_reference or load_curriculum_reference()
    reference_by_code = {item["code"]: item for item in reference.get("standards", [])}
    for standard in plan["standards"]:
        if standard["code"] not in reference_by_code:
            errors.append(
                {
                    "code": "curriculum_code_unknown",
                    "message": f"standard code is not in curriculum reference: {standard['code']}",
                }
            )

    if assessment is not None:
        normalized = normalize_assessment(assessment)
        if plan["assessment_id"] != normalized["assessment_id"]:
            errors.append(
                {
                    "code": "assessment_id_mismatch",
                    "message": "lesson plan and assessment IDs differ",
                }
            )
        condition_ids = _assessment_condition_ids(normalized)
        map_text = " ".join(plan["answer_planning"]["condition_to_sentence_map"])
        teaching_text = " ".join(_all_strings(plan["sequence"]))
        missing_conditions = [
            item for item in condition_ids if item not in f"{map_text} {teaching_text}"
        ]
        if missing_conditions:
            errors.append(
                {
                    "code": "condition_not_planned",
                    "message": "conditions are missing from answer planning: "
                    f"{', '.join(sorted(missing_conditions))}",
                }
            )
        total_points = float(normalized["metadata"]["total_points"])
        answer_ids = _assessment_answer_ids(normalized)
        for anchor in plan["scoring_anchors"]:
            if anchor["score"] > total_points:
                errors.append(
                    {
                        "code": "anchor_score_out_of_range",
                        "message": f"scoring anchor {anchor['score']} exceeds "
                        f"total {total_points:g}",
                    }
                )
            if anchor.get("answer_id") and anchor["answer_id"] not in answer_ids:
                warnings.append(
                    {
                        "code": "anchor_answer_unknown",
                        "message": "scoring anchor references unknown answer "
                        f"{anchor['answer_id']}",
                    }
                )
        assessment_report = validate_assessment(normalized)
        if not assessment_report["ok"]:
            errors.append(
                {
                    "code": "assessment_invalid",
                    "message": "linked assessment does not pass deterministic validation",
                    "details": assessment_report["errors"],
                }
            )

    placeholder_or_emoji = [
        text for text in _all_strings(plan) if has_placeholder(text) or EMOJI_RE.search(text)
    ]
    if placeholder_or_emoji:
        errors.append(
            {
                "code": "presentation_placeholder_or_emoji",
                "message": "lesson plan contains an unresolved placeholder or emoji",
                "details": {"count": len(placeholder_or_emoji)},
            }
        )

    checks = [
        {
            "id": "sequence_duration",
            "status": "pass" if minutes_total == duration else "fail",
            "actual": minutes_total,
            "expected": duration,
        },
        {
            "id": "curriculum_codes",
            "status": "pass"
            if not any(item["code"] == "curriculum_code_unknown" for item in errors)
            else "fail",
        },
        {
            "id": "question_response_checks",
            "status": "pass"
            if not any(
                item["code"] in {"question_response_mismatch", "question_check_mismatch"}
                for item in errors
            )
            else "fail",
        },
    ]
    return {
        "ok": not errors,
        "assessment_id": plan["assessment_id"],
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }
