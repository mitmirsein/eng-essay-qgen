#!/usr/bin/env python3
"""Validate an assessment package and optionally write qa-report.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from eng_essay_qgen.package_io import AssessmentIOError, load_assessment  # noqa: E402
from eng_essay_qgen.validators import validate_assessment, validate_student_security  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an eng-essay-qgen assessment package")
    parser.add_argument("assessment", help="path to assessment.json")
    parser.add_argument("--report", help="write the QA JSON report to this path")
    parser.add_argument("--student-output", help="also scan a rendered student Markdown file")
    args = parser.parse_args()

    try:
        assessment = load_assessment(args.assessment)
    except (AssessmentIOError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    report = validate_assessment(assessment)
    if args.student_output:
        try:
            student_text = Path(args.student_output).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"ERROR: cannot read student output: {exc}", file=sys.stderr)
            return 2
        security = validate_student_security(
            student_text, model_answers=assessment.get("model_answers", [])
        )
        report["student_security"] = security
        if not security["ok"]:
            report["ok"] = False
            report["errors"].extend(security["errors"])

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    status = "PASS" if report["ok"] else "FAIL"
    print(f"{status}: {report.get('assessment_id', args.assessment)}")
    check_count = len(report.get("checks", []))
    error_count = len(report.get("errors", []))
    warning_count = len(report.get("warnings", []))
    print(f"  checks={check_count} errors={error_count} warnings={warning_count}")
    for error in report.get("errors", []):
        print(f"  - {error['code']}: {error['message']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
