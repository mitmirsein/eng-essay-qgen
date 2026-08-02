"""Allowlist-based Markdown renderers for student and teacher views."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .package_io import PROJECT_ROOT, normalize_assessment
from .validators import validate_student_security

RenderTarget = Literal["student", "teacher"]


class RenderSecurityError(ValueError):
    """Raised when a student view fails the post-render security scan."""


def _points(value: float | int) -> str:
    return f"{value:g}" if isinstance(value, (int, float)) else str(value)


def _passage_view(assessment: dict[str, Any]) -> dict[str, Any]:
    passage = assessment["passage"]
    return {
        "text": passage["text"],
        "sections": [
            {"id": item["id"], "text": item["text"]}
            for item in passage.get("sections", [])
            if isinstance(item, dict) and item.get("id") and item.get("text")
        ],
    }


def _conditions_view(conditions: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{"id": item["id"], "text": item["text_ko"]} for item in conditions]


def _rubric_view(rubric: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": item["id"],
            "condition_ids": item["condition_ids"],
            "points": _points(item["points"]),
            "full_credit": item["full_credit_ko"],
            "partial_credit": item.get("partial_credit_ko", ""),
        }
        for item in rubric
    ]


def _level_view(level: dict[str, Any]) -> dict[str, Any]:
    rubric = _rubric_view(level.get("rubric", []))
    return {
        "id": level["id"],
        "label": level["label"],
        "instruction": level["instruction_ko"],
        "points": _points(sum(float(item["points"]) for item in level.get("rubric", []))),
        "conditions": _conditions_view(level.get("conditions", [])),
        "rubric": rubric,
        "answers": [
            {"level": item["level"], "text": item["text"]}
            for item in level.get("model_answers", [])
        ],
    }


def student_context(assessment: dict[str, Any]) -> dict[str, Any]:
    """Build a student-only view; no answers, rubric, or full assessment is passed."""

    normalized = normalize_assessment(assessment)
    metadata = normalized["metadata"]
    passage = _passage_view(normalized)
    levels = [_level_view(level) for level in normalized.get("differentiated_levels", [])]
    return {
        "title": metadata["title"],
        "grade": metadata["grade"],
        "total_points": _points(metadata["total_points"]),
        "instruction": normalized["task"]["instruction_ko"],
        "passage_text": passage["text"],
        "passage_sections": passage["sections"],
        "conditions": _conditions_view(normalized.get("conditions", [])),
        "levels": [
            {
                "label": level["label"],
                "instruction": level["instruction"],
                "points": level["points"],
                "conditions": level["conditions"],
            }
            for level in levels
        ],
    }


def teacher_context(assessment: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_assessment(assessment)
    metadata = normalized["metadata"]
    passage = _passage_view(normalized)
    return {
        "title": metadata["title"],
        "topic": metadata["topic"],
        "grade": metadata["grade"],
        "question_type": metadata["question_type"],
        "total_points": _points(metadata["total_points"]),
        "instruction": normalized["task"]["instruction_ko"],
        "passage_text": passage["text"],
        "conditions": _conditions_view(normalized.get("conditions", [])),
        "rubric_items": _rubric_view(normalized.get("rubric", [])),
        "answers": [
            {
                "level": item["level"],
                "text": item["text"],
                "rationale": item.get("rationale_ko", ""),
            }
            for item in normalized.get("model_answers", [])
        ],
        "levels": [_level_view(level) for level in normalized.get("differentiated_levels", [])],
        "lesson_plan": normalized.get("lesson_plan"),
    }


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(PROJECT_ROOT / "templates")),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
        trim_blocks=False,
        lstrip_blocks=False,
    )


def render_markdown(assessment: dict[str, Any], target: RenderTarget) -> str:
    environment = _environment()
    if target == "student":
        rendered = environment.get_template("student_exam.md.j2").render(
            **student_context(assessment)
        )
        private_answers = list(assessment.get("model_answers", []))
        for level in assessment.get("differentiated_levels", []):
            private_answers.extend(level.get("model_answers", []))
        security = validate_student_security(rendered, model_answers=private_answers)
        if not security["ok"]:
            details = "; ".join(item["message"] for item in security["errors"])
            raise RenderSecurityError(f"student render blocked: {details}")
        return rendered
    if target == "teacher":
        return environment.get_template("teacher_guide.md.j2").render(**teacher_context(assessment))
    raise ValueError(f"unsupported render target: {target}")


def write_rendered_package(
    assessment: dict[str, Any],
    output_dir: str | Path,
    *,
    target: Literal["student", "teacher", "all"] = "all",
    overwrite: bool = False,
) -> list[Path]:
    directory = Path(output_dir)
    targets = ["student", "teacher"] if target == "all" else [target]
    outputs: list[Path] = []
    for item in targets:
        destination = directory / f"{item}.md"
        if destination.exists() and not overwrite:
            raise FileExistsError(f"refusing to overwrite rendered file: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_markdown(assessment, item), encoding="utf-8")
        outputs.append(destination)
    return outputs
