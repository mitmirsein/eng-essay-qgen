"""Teacher profile, index, HITL batch, class insight, and stale-state helpers."""

from __future__ import annotations

import csv
import hashlib
import html
import json
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from .package_io import GRADE_ALIASES, PROJECT_ROOT

PROFILE_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "teacher-profile.schema.json"
EXAMPLE_PROFILE_PATH = PROJECT_ROOT / "config" / "teacher_profile.example.yaml"
LOCAL_PROFILE_PATH = PROJECT_ROOT / "config" / "teacher_profile.local.yaml"
BATCH_STATES = {
    "pending-extraction",
    "pending-review",
    "corrected",
    "approved",
    "graded",
    "failed",
}
ALLOWED_TRANSITIONS = {
    "pending-extraction": {"pending-review", "failed"},
    "pending-review": {"corrected", "approved", "failed"},
    "corrected": {"approved", "graded", "failed"},
    "approved": {"graded", "failed"},
    "graded": set(),
    "failed": {"pending-extraction"},
}
STALE_DEPENDENCIES = {
    "passage": {
        "task_conditions",
        "rubric",
        "model_answers",
        "lesson_sequence",
        "differentiation",
        "scoring_anchors",
        "student_pdf",
        "teacher_pdf",
        "feedback_pdf",
    },
    "task_conditions": {
        "rubric",
        "model_answers",
        "lesson_sequence",
        "differentiation",
        "scoring_anchors",
        "student_pdf",
        "teacher_pdf",
        "feedback_pdf",
    },
    "model_answers": {"scoring_anchors", "teacher_pdf", "feedback_pdf"},
    "lesson_sequence": {"teacher_pdf"},
    "differentiation": {"teacher_pdf"},
    "scoring_anchors": {"teacher_pdf", "feedback_pdf"},
    "pdfs": {"student_pdf", "teacher_pdf", "feedback_pdf"},
}


def _profile_schema_errors(profile: dict[str, Any]) -> list[str]:
    schema = json.loads(PROFILE_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    return [error.message for error in validator.iter_errors(profile)]


def _normalize_profile(profile: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(profile)
    grade = normalized.get("default_grade")
    if isinstance(grade, str):
        normalized["default_grade"] = GRADE_ALIASES.get(grade, grade)
    ratio = normalized.get("instruction_language_ratio", {})
    if ratio and ratio.get("korean", 0) + ratio.get("english", 0) != 100:
        raise ValueError("instruction_language_ratio korean + english must equal 100")
    return normalized


def load_teacher_profile(path: str | Path | None = None) -> dict[str, Any]:
    source = (
        Path(path)
        if path
        else (LOCAL_PROFILE_PATH if LOCAL_PROFILE_PATH.exists() else EXAMPLE_PROFILE_PATH)
    )
    data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("teacher profile YAML must contain an object")
    profile = _normalize_profile(data)
    errors = _profile_schema_errors(profile)
    if errors:
        raise ValueError("teacher profile validation failed: " + "; ".join(errors))
    return profile


def merge_profile(
    profile: dict[str, Any], overrides: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Deep-merge explicit CLI overrides over the loaded teacher profile."""

    result = deepcopy(profile)

    def merge(target: dict[str, Any], values: dict[str, Any]) -> None:
        for key, value in values.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                merge(target[key], value)
            else:
                target[key] = value

    merge(result, overrides or {})
    normalized = _normalize_profile(result)
    errors = _profile_schema_errors(normalized)
    if errors:
        raise ValueError("merged teacher profile validation failed: " + "; ".join(errors))
    return normalized


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def build_teacher_index(root: str | Path) -> dict[str, Any]:
    """Build an index from manifests only; never infer artifacts from filenames."""

    base = Path(root)
    items = []
    for manifest_path in sorted(base.rglob("manifest.json")):
        manifest = _read_json(manifest_path)
        if not manifest:
            continue
        artifact_paths = [item.get("path") for item in manifest.get("outputs", [])]
        metadata = manifest.get("assessment_metadata", {})
        stale_sections = manifest.get("stale_sections", [])
        items.append(
            {
                "assessment_id": manifest.get("assessment_id"),
                "schema_version": manifest.get("schema_version"),
                "title": metadata.get("title"),
                "topic": metadata.get("topic"),
                "grade": metadata.get("grade"),
                "question_type": metadata.get("question_type"),
                "generated_at": manifest.get("generated_at"),
                "last_modified": manifest.get("last_modified", manifest.get("generated_at")),
                "qa_status": manifest.get("qa_status", "unknown"),
                "stale_sections": stale_sections,
                "regeneration_required": bool(stale_sections),
                "artifacts": [path for path in artifact_paths if path],
                "manifest_path": str(manifest_path),
                "has_grading": any("grading" in str(path) for path in artifact_paths),
                "has_coaching": any("coaching" in str(path) for path in artifact_paths),
                "has_class_insights": any("class-insights" in str(path) for path in artifact_paths),
            }
        )
    return {
        "index_version": "1.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "root": str(base),
        "items": items,
    }


def render_index_markdown(index: dict[str, Any]) -> str:
    lines = ["# 강사용 산출물 인덱스", "", f"생성 시각: {index['generated_at']}", ""]
    if not index["items"]:
        return "\n".join(lines + ["산출물이 없습니다.", ""])
    lines.extend(
        [
            "| 평가 ID | 주제 | 학년 | 유형 | QA | 재생성 필요 | 산출물 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in index["items"]:
        artifacts = ", ".join(item["artifacts"]) or "-"
        lines.append(
            f"| {item['assessment_id']} | {item.get('topic') or '-'} | "
            f"{item.get('grade') or '-'} | "
            f"{item.get('question_type') or '-'} | {item['qa_status']} | "
            f"{'예' if item['regeneration_required'] else '아니오'} | {artifacts} |"
        )
    return "\n".join(lines) + "\n"


def render_index_html(index: dict[str, Any]) -> str:
    rows = []
    for item in index["items"]:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(item['assessment_id']))}</td>"
            f"<td>{html.escape(str(item.get('topic') or '-'))}</td>"
            f"<td>{html.escape(str(item.get('grade') or '-'))}</td>"
            f"<td>{html.escape(str(item.get('question_type') or '-'))}</td>"
            f"<td>{html.escape(str(item['qa_status']))}</td>"
            f"<td>{html.escape('예' if item['regeneration_required'] else '아니오')}</td>"
            f"<td>{html.escape(', '.join(item['artifacts']) or '-')}</td>"
            "</tr>"
        )
    return (
        "<!doctype html><meta charset='utf-8'><title>강사용 산출물 인덱스</title>"
        "<h1>강사용 산출물 인덱스</h1>"
        "<table><thead><tr><th>평가 ID</th><th>주제</th><th>학년</th><th>유형</th>"
        "<th>QA</th><th>재생성 필요</th><th>산출물</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def write_teacher_index(
    root: str | Path, destination: str | Path, *, format: str = "markdown"
) -> Path:
    index = build_teacher_index(root)
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        render_index_html(index) if format == "html" else render_index_markdown(index),
        encoding="utf-8",
    )
    return target


def anonymous_student_id(source_path: str | Path, *, salt: str = "eng-essay-qgen") -> str:
    canonical_source = str(Path(source_path).resolve())
    digest = hashlib.sha256(f"{salt}:{canonical_source}".encode()).hexdigest()
    return f"stu-{digest[:12]}"


def init_batch(
    batch_id: str,
    source_paths: Iterable[str | Path],
    output_root: str | Path,
    *,
    retain_handwriting_images: bool = False,
    resume: bool = False,
) -> Path:
    batch_dir = Path(output_root) / batch_id
    if batch_dir.exists():
        if (
            resume
            and (batch_dir / "batch-manifest.json").exists()
            and (batch_dir / "approvals.json").exists()
        ):
            return batch_dir
        raise FileExistsError(f"batch already exists: {batch_dir}")
    batch_dir.mkdir(parents=True)
    items = []
    source_map = {}
    for source in source_paths:
        source_path = Path(source)
        student_id = anonymous_student_id(source_path)
        source_key = hashlib.sha256(str(source_path.resolve()).encode("utf-8")).hexdigest()[:16]
        source_map[source_key] = str(source_path.resolve())
        items.append(
            {
                "anonymous_id": student_id,
                "source_key": source_key,
                "status": "pending-extraction",
                "uncertain_spans": [],
            }
        )
    manifest = {
        "batch_version": "1.0.0",
        "batch_id": batch_id,
        "created_at": datetime.now(UTC).isoformat(),
        "item_count": len(items),
        "retain_handwriting_images": retain_handwriting_images,
        "uses_anonymous_student_ids": True,
    }
    (batch_dir / "batch-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (batch_dir / "approvals.json").write_text(
        json.dumps({"items": items}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (batch_dir / "source_map.local.json").write_text(
        json.dumps(source_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (batch_dir / "transcriptions.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "anonymous_id",
                "source_key",
                "status",
                "transcript",
                "uncertain_spans",
                "note",
            ],
        )
        writer.writeheader()
        for item in items:
            writer.writerow({**item, "transcript": "", "uncertain_spans": "", "note": ""})
    (batch_dir / "reports").mkdir()
    return batch_dir


def _load_approvals(batch_dir: Path) -> dict[str, Any]:
    data = _read_json(batch_dir / "approvals.json")
    if not data or not isinstance(data.get("items"), list):
        raise ValueError(f"invalid approvals file: {batch_dir / 'approvals.json'}")
    return data


def _sync_transcriptions(batch_dir: Path, item: dict[str, Any]) -> None:
    path = batch_dir / "transcriptions.csv"
    if not path.exists():
        return
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        if row.get("anonymous_id") == item["anonymous_id"]:
            row["status"] = item["status"]
            row["transcript"] = item.get("transcript", "")
            row["uncertain_spans"] = json.dumps(item.get("uncertain_spans", []), ensure_ascii=False)
            row["note"] = item.get("note", "")
    with path.open("w", encoding="utf-8", newline="") as stream:
        fieldnames = [
            "anonymous_id",
            "source_key",
            "status",
            "transcript",
            "uncertain_spans",
            "note",
        ]
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def transition_batch_item(
    batch_dir: str | Path,
    anonymous_id: str,
    new_status: str,
    *,
    transcript: str | None = None,
    uncertain_spans: list[str] | None = None,
    note: str = "",
) -> dict[str, Any]:
    if new_status not in BATCH_STATES:
        raise ValueError(f"unsupported batch status: {new_status}")
    directory = Path(batch_dir)
    approvals = _load_approvals(directory)
    item = next((item for item in approvals["items"] if item["anonymous_id"] == anonymous_id), None)
    if not item:
        raise KeyError(f"unknown anonymous student id: {anonymous_id}")
    current = item["status"]
    if new_status not in ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"invalid batch transition: {current} -> {new_status}")
    item["status"] = new_status
    if transcript is not None:
        item["transcript"] = transcript
    if uncertain_spans is not None:
        item["uncertain_spans"] = uncertain_spans
    if note:
        item["note"] = note
    item["updated_at"] = datetime.now(UTC).isoformat()
    (directory / "approvals.json").write_text(
        json.dumps(approvals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _sync_transcriptions(directory, item)
    return item


def eligible_for_grading(batch_dir: str | Path) -> list[dict[str, Any]]:
    approvals = _load_approvals(Path(batch_dir))
    return [item for item in approvals["items"] if item["status"] in {"approved", "corrected"}]


def _float_score(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "pass", "passed"}
    return bool(value)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def summarize_class(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    records = list(rows)
    scores = [_float_score(row.get("score")) for row in records]
    totals = [_float_score(row.get("total_points")) for row in records]
    condition_hits: defaultdict[str, list[bool]] = defaultdict(list)
    error_counts: Counter[str] = Counter()
    for row in records:
        conditions = _as_dict(row.get("conditions", {}))
        for condition_id, passed in conditions.items():
            condition_hits[condition_id].append(_as_bool(passed))
        tags = row.get("error_tags", [])
        if isinstance(tags, str):
            try:
                decoded_tags = json.loads(tags)
            except json.JSONDecodeError:
                decoded_tags = [tags]
            tags = decoded_tags if isinstance(decoded_tags, list) else [str(decoded_tags)]
        error_counts.update(str(tag) for tag in tags)
    distribution = Counter(f"{score:g}" for score in scores)
    condition_rates = {
        condition_id: sum(hits) / len(hits) if hits else 0.0
        for condition_id, hits in sorted(condition_hits.items())
    }
    reteach = [condition_id for condition_id, rate in condition_rates.items() if rate < 0.7]
    reteach_recommendations = [
        {
            "condition_id": condition_id,
            "mini_lesson": f"재수업: {condition_id}의 근거 찾기와 자기점검을 짧게 다시 지도한다.",
        }
        for condition_id in reteach
    ]
    strong_candidates = [
        str(row["anonymous_id"])
        for row in records
        if row.get("anonymous_id")
        and _float_score(row.get("total_points")) > 0
        and _float_score(row.get("score")) >= 0.8 * _float_score(row.get("total_points"))
    ]
    return {
        "summary_version": "1.0.0",
        "student_count": len(records),
        "average_score": statistics.mean(scores) if scores else 0.0,
        "median_score": statistics.median(scores) if scores else 0.0,
        "average_total_points": statistics.mean(totals) if totals else 0.0,
        "score_distribution": dict(sorted(distribution.items())),
        "condition_attainment": condition_rates,
        "error_patterns": dict(error_counts.most_common()),
        "reteach_conditions": reteach,
        "reteach_recommendations": reteach_recommendations,
        "strong_answer_candidates": strong_candidates,
        "privacy": {"student_names_included": False, "uses_anonymous_ids": True},
    }


def write_class_summary(
    rows: Iterable[dict[str, Any]], output_dir: str | Path
) -> tuple[Path, Path]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    summary = summarize_class(rows)
    json_path = directory / "class-summary.json"
    csv_path = directory / "class-summary.csv"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["metric", "value"])
        for key in ["student_count", "average_score", "median_score", "average_total_points"]:
            writer.writerow([key, summary[key]])
        for condition_id, rate in summary["condition_attainment"].items():
            writer.writerow([f"condition:{condition_id}", rate])
        for error_tag, count in summary["error_patterns"].items():
            writer.writerow([f"error:{error_tag}", count])
        for recommendation in summary["reteach_recommendations"]:
            writer.writerow(
                [f"reteach:{recommendation['condition_id']}", recommendation["mini_lesson"]]
            )
        for anonymous_id in summary["strong_answer_candidates"]:
            writer.writerow(["strong_candidate", anonymous_id])
    return json_path, csv_path


def mark_stale(manifest_path: str | Path, changed_section: str) -> dict[str, Any]:
    if changed_section not in STALE_DEPENDENCIES:
        raise ValueError(f"unknown changed section: {changed_section}")
    path = Path(manifest_path)
    manifest = _read_json(path)
    if not manifest:
        raise ValueError(f"invalid manifest: {path}")
    stale = set(manifest.get("stale_sections", []))
    stale.update(STALE_DEPENDENCIES[changed_section])
    manifest["stale_sections"] = sorted(stale)
    manifest["last_modified"] = datetime.now(UTC).isoformat()
    manifest.setdefault("events", []).append(
        {
            "type": "stale-propagation",
            "changed_section": changed_section,
            "stale_sections": sorted(STALE_DEPENDENCIES[changed_section]),
            "at": datetime.now(UTC).isoformat(),
        }
    )
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
