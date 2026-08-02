#!/usr/bin/env python3
"""Render student and/or teacher Markdown views from one assessment package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from eng_essay_qgen.lesson_plans import load_lesson_plan, validate_lesson_plan  # noqa: E402
from eng_essay_qgen.manifests import build_manifest, write_manifest  # noqa: E402
from eng_essay_qgen.package_io import AssessmentIOError, load_assessment  # noqa: E402
from eng_essay_qgen.renderers import RenderSecurityError, write_rendered_package  # noqa: E402
from eng_essay_qgen.teacher_ops import load_teacher_profile, merge_profile  # noqa: E402
from eng_essay_qgen.validators import validate_assessment  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Render safe assessment package views")
    parser.add_argument("assessment", help="path to assessment.json")
    parser.add_argument("--target", choices=["student", "teacher", "all"], default="all")
    parser.add_argument("--output", required=True, help="output directory for rendered views")
    parser.add_argument(
        "--lesson-plan",
        help="optional lesson-plan.json to embed in the teacher view",
    )
    parser.add_argument("--teacher-profile", help="optional teacher profile YAML")
    parser.add_argument(
        "--profile-override",
        default="{}",
        help="JSON object of teacher-profile overrides",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    try:
        assessment = load_assessment(args.assessment)
    except (AssessmentIOError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    report = validate_assessment(assessment)
    if not report["ok"]:
        print("ERROR: assessment validation failed", file=sys.stderr)
        for error in report["errors"]:
            print(f"- {error['message']}", file=sys.stderr)
        return 1

    input_paths = [args.assessment]
    teacher_profile = None
    if args.teacher_profile or args.profile_override != "{}":
        try:
            overrides = json.loads(args.profile_override)
            if not isinstance(overrides, dict):
                raise ValueError("--profile-override must be a JSON object")
            teacher_profile = merge_profile(load_teacher_profile(args.teacher_profile), overrides)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"ERROR: teacher profile could not be applied: {exc}", file=sys.stderr)
            return 2
    if args.lesson_plan:
        try:
            lesson_plan = load_lesson_plan(args.lesson_plan)
        except (OSError, ValueError) as exc:
            print(f"ERROR: lesson plan could not be loaded: {exc}", file=sys.stderr)
            return 2
        lesson_report = validate_lesson_plan(lesson_plan, assessment=assessment)
        if not lesson_report["ok"]:
            print("ERROR: lesson plan validation failed", file=sys.stderr)
            for error in lesson_report["errors"]:
                print(f"- {error['message']}", file=sys.stderr)
            return 1
        assessment["lesson_plan"] = lesson_plan
        input_paths.append(args.lesson_plan)

    output_dir = Path(args.output)
    try:
        outputs = write_rendered_package(
            assessment,
            output_dir,
            target=args.target,
            overwrite=args.overwrite,
        )
    except (FileExistsError, RenderSecurityError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    report_path = output_dir / "qa-report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest = build_manifest(
        assessment_id=assessment["assessment_id"],
        schema_version=assessment["schema_version"],
        package_dir=output_dir,
        input_paths=input_paths,
        output_paths=[*outputs, report_path],
        qa_status="pass",
        metadata=assessment["metadata"],
        teacher_profile=teacher_profile,
    )
    write_manifest(manifest, output_dir / "manifest.json", overwrite=True)
    print(f"Rendered {len(outputs)} file(s) to {output_dir}")
    for output in outputs:
        print(f"- {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
