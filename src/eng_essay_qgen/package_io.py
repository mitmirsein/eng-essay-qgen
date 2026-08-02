"""Read, normalize, and safely write private assessment packages."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "assessment-package.schema.json"
DEFAULT_PACKAGE_ROOT = PROJECT_ROOT / "output" / "lesson-plans" / "_packages"

GRADE_ALIASES = {"고2": "고2/3", "고3": "고2/3"}
CANONICAL_GRADES = {"중1", "중2", "중3", "고1", "고2/3"}
ASSESSMENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")


class AssessmentIOError(ValueError):
    """Raised when an assessment cannot be safely read or written."""


def normalize_grade(value: str) -> str:
    """Normalize the project-specific high-school grade aliases."""

    if not isinstance(value, str):
        raise AssessmentIOError("metadata.grade must be a string")
    normalized = GRADE_ALIASES.get(value.strip(), value.strip())
    if normalized not in CANONICAL_GRADES:
        raise AssessmentIOError(
            f"unsupported grade {value!r}; expected one of {sorted(CANONICAL_GRADES)}"
        )
    return normalized


def normalize_assessment(assessment: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized deep copy without dropping extension fields."""

    if not isinstance(assessment, dict):
        raise AssessmentIOError("assessment must be a JSON object")
    normalized = copy.deepcopy(assessment)
    metadata = normalized.get("metadata")
    if isinstance(metadata, dict) and "grade" in metadata:
        metadata["grade"] = normalize_grade(metadata["grade"])
    return normalized


def load_schema() -> dict[str, Any]:
    try:
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AssessmentIOError(f"schema not found: {SCHEMA_PATH}") from exc


def schema_errors(assessment: dict[str, Any]) -> list[str]:
    """Return stable, human-readable JSON Schema errors."""

    validator = Draft202012Validator(load_schema())
    errors = []
    for error in sorted(validator.iter_errors(assessment), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.path) or "$"
        errors.append(f"{location}: {error.message}")
    return errors


def load_assessment(path: str | Path, *, validate: bool = True) -> dict[str, Any]:
    """Load a UTF-8 assessment JSON file, normalizing grade aliases."""

    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AssessmentIOError(f"assessment file not found: {source}") from exc
    except json.JSONDecodeError as exc:
        raise AssessmentIOError(f"invalid JSON in {source}: {exc}") from exc
    normalized = normalize_assessment(raw)
    if validate:
        errors = schema_errors(normalized)
        if errors:
            raise AssessmentIOError(
                "assessment schema validation failed:\n- " + "\n- ".join(errors)
            )
    return normalized


def _resolved_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def assert_safe_package_path(
    path: str | Path,
    assessment_id: str,
    *,
    package_root: str | Path | None = None,
) -> Path:
    """Validate that a package file is inside an explicitly allowed package root."""

    if not ASSESSMENT_ID_RE.fullmatch(assessment_id):
        raise AssessmentIOError(f"invalid assessment_id: {assessment_id!r}")
    target = Path(path)
    root = Path(package_root) if package_root is not None else DEFAULT_PACKAGE_ROOT
    root = root.resolve()
    resolved = target.resolve()
    if not _resolved_within(resolved, root):
        raise AssessmentIOError(f"package path escapes allowed root {root}: {target}")
    if resolved.name != "assessment.json":
        raise AssessmentIOError("assessment packages must be stored as assessment.json")
    if resolved.parent.name != assessment_id:
        raise AssessmentIOError(
            f"package directory {resolved.parent.name!r} does not match "
            f"assessment_id {assessment_id!r}"
        )
    return target


def save_assessment(
    assessment: dict[str, Any],
    path: str | Path,
    *,
    overwrite: bool = False,
    package_root: str | Path | None = None,
) -> Path:
    """Validate and write an assessment without accidental overwrites."""

    normalized = normalize_assessment(assessment)
    assessment_id = normalized.get("assessment_id")
    if not isinstance(assessment_id, str):
        raise AssessmentIOError("assessment_id is required before writing")
    target = assert_safe_package_path(path, assessment_id, package_root=package_root)
    errors = schema_errors(normalized)
    if errors:
        raise AssessmentIOError("assessment schema validation failed:\n- " + "\n- ".join(errors))
    if target.exists() and not overwrite:
        raise AssessmentIOError(f"refusing to overwrite existing file: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target
