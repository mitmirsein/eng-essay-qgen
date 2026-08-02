"""Manifest and content-hash helpers for assessment package artifacts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_record(path: Path, package_dir: Path) -> dict[str, Any]:
    try:
        relative = path.resolve().relative_to(package_dir.resolve())
    except ValueError:
        relative = path
    return {
        "path": str(relative),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def build_manifest(
    *,
    assessment_id: str,
    schema_version: str,
    package_dir: str | Path,
    input_paths: Iterable[str | Path] = (),
    output_paths: Iterable[str | Path] = (),
    qa_status: str = "pending",
    stale_sections: Iterable[str] = (),
    metadata: dict[str, Any] | None = None,
    teacher_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    package = Path(package_dir)
    inputs = [Path(item) for item in input_paths if Path(item).exists()]
    outputs = [Path(item) for item in output_paths if Path(item).exists()]
    safe_metadata = {
        key: metadata[key]
        for key in ("title", "topic", "grade", "question_type", "total_points")
        if metadata and key in metadata
    }
    profile_keys = (
        "default_grade",
        "lesson_duration_minutes",
        "class_size",
        "proficiency_profile",
        "instruction_language_ratio",
        "default_total_points",
        "language_penalty",
        "pdf_profile",
        "output_formats",
        "privacy",
    )
    safe_profile = {
        key: teacher_profile[key]
        for key in profile_keys
        if teacher_profile and key in teacher_profile
    }
    return {
        "manifest_version": "1.0.0",
        "assessment_id": assessment_id,
        "schema_version": schema_version,
        "generated_at": datetime.now(UTC).isoformat(),
        "last_modified": datetime.now(UTC).isoformat(),
        "qa_status": qa_status,
        "stale_sections": list(stale_sections),
        "assessment_metadata": safe_metadata,
        "teacher_profile": safe_profile,
        "inputs": [_artifact_record(path, package) for path in inputs],
        "outputs": [_artifact_record(path, package) for path in outputs],
    }


def write_manifest(
    manifest: dict[str, Any],
    path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    target = Path(path)
    if target.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing manifest: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target
