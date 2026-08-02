#!/usr/bin/env python3
"""Export dated sample Markdown, PDF, and private package artifacts."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from eng_essay_qgen.manifests import build_manifest, write_manifest  # noqa: E402
from eng_essay_qgen.package_io import (  # noqa: E402
    DEFAULT_PACKAGE_ROOT,
    AssessmentIOError,
    save_assessment,
)
from eng_essay_qgen.renderers import render_markdown  # noqa: E402
from eng_essay_qgen.validators import validate_assessment  # noqa: E402
from scripts.migrate_samples import SAMPLE_SPECS, migrate_one  # noqa: E402

PDF_TOOL = PROJECT_ROOT / "tools" / "exam-pdf" / "make_exam_pdf.py"
DATE_RE = re.compile(r"^\d{8}$")


def _dated_id(legacy_id: str, date_prefix: str) -> str:
    return f"{date_prefix}{legacy_id[8:]}"


def _pdf(
    markdown: Path,
    output: Path,
    *,
    title: str,
    subtitle: str,
    profile: str,
    total_points: int | None,
) -> None:
    command = [
        sys.executable,
        str(PDF_TOOL),
        str(markdown),
        "--profile",
        profile,
        "--title",
        title,
        "--subtitle",
        subtitle,
        "-o",
        str(output),
    ]
    if total_points is not None:
        command.extend(["--total-points", str(total_points)])
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "PDF build failed")
    if result.stdout.strip():
        print(result.stdout.strip())


def export_one(
    legacy_id: str,
    *,
    date_prefix: str,
    package_root: Path,
    public_question_root: Path,
    public_lesson_root: Path,
    overwrite: bool,
) -> tuple[Path, Path, Path, Path, Path]:
    assessment = migrate_one(legacy_id)
    assessment_id = _dated_id(legacy_id, date_prefix)
    assessment["assessment_id"] = assessment_id
    assessment["metadata"]["created_at"] = datetime.now(UTC).isoformat()

    package_dir = package_root / assessment_id
    assessment_path = package_dir / "assessment.json"
    student_md = public_question_root / f"{assessment_id}.md"
    teacher_md = public_lesson_root / f"{assessment_id}_lesson.md"
    student_pdf = student_md.with_suffix(".pdf")
    teacher_pdf = teacher_md.with_suffix(".pdf")
    destinations = [assessment_path, student_md, teacher_md, student_pdf, teacher_pdf]
    if not overwrite:
        existing = [str(path) for path in destinations if path.exists()]
        if existing:
            raise FileExistsError("refusing to overwrite: " + ", ".join(existing))

    save_assessment(assessment, assessment_path, overwrite=overwrite, package_root=package_root)
    report = validate_assessment(assessment)
    if not report["ok"]:
        raise ValueError(f"{assessment_id}: assessment validation failed: {report['errors']}")
    package_dir.mkdir(parents=True, exist_ok=True)
    qa_report = package_dir / "qa-report.json"
    qa_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    public_question_root.mkdir(parents=True, exist_ok=True)
    public_lesson_root.mkdir(parents=True, exist_ok=True)
    student_md.write_text(render_markdown(assessment, "student"), encoding="utf-8")
    teacher_md.write_text(render_markdown(assessment, "teacher"), encoding="utf-8")

    grade = assessment["metadata"]["grade"]
    differentiated = assessment["metadata"]["question_type"] == "differentiated"
    student_title = "수준별 영어 서술형 평가" if differentiated else "영어 서술형 평가"
    teacher_title = "수준별 서술형 교사용 지도안" if differentiated else "교사용 수업 지도안"
    _pdf(
        student_md,
        student_pdf,
        title=student_title,
        subtitle=f"{grade} 대비",
        profile="exam",
        total_points=8,
    )
    _pdf(
        teacher_md,
        teacher_pdf,
        title=teacher_title,
        subtitle=f"{grade} 영어 서술형 대비",
        profile="teacher",
        total_points=None,
    )

    manifest = build_manifest(
        assessment_id=assessment_id,
        schema_version=assessment["schema_version"],
        package_dir=package_dir,
        output_paths=[assessment_path, student_md, teacher_md, student_pdf, teacher_pdf, qa_report],
        qa_status="pass",
        metadata=assessment["metadata"],
    )
    write_manifest(manifest, package_dir / "manifest.json", overwrite=True)
    print(f"exported: {assessment_id}")
    return student_md, student_pdf, teacher_md, teacher_pdf, package_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Export dated sample outputs")
    parser.add_argument("--date", default=datetime.now(UTC).strftime("%Y%m%d"))
    parser.add_argument("--sample", choices=[*SAMPLE_SPECS, "all"], default="all")
    parser.add_argument("--package-root", default=str(DEFAULT_PACKAGE_ROOT))
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if not DATE_RE.fullmatch(args.date):
        parser.error("--date must be YYYYMMDD")

    selected = list(SAMPLE_SPECS) if args.sample == "all" else [args.sample]
    try:
        for legacy_id in selected:
            export_one(
                legacy_id,
                date_prefix=args.date,
                package_root=Path(args.package_root),
                public_question_root=PROJECT_ROOT / "output" / "essay-questions",
                public_lesson_root=PROJECT_ROOT / "output" / "lesson-plans",
                overwrite=args.overwrite,
            )
    except (AssessmentIOError, FileExistsError, OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
