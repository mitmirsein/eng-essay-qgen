#!/usr/bin/env python3
"""Validate lesson-plan.json against schema and optional assessment package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from eng_essay_qgen.lesson_plans import load_lesson_plan, validate_lesson_plan  # noqa: E402
from eng_essay_qgen.package_io import load_assessment  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate lesson-plan.json")
    parser.add_argument("lesson_plan")
    parser.add_argument("--assessment")
    parser.add_argument("--report")
    args = parser.parse_args()
    try:
        plan = load_lesson_plan(args.lesson_plan)
        assessment = load_assessment(args.assessment) if args.assessment else None
        report = validate_lesson_plan(plan, assessment=assessment)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(f"{'PASS' if report['ok'] else 'FAIL'}: {report.get('assessment_id', args.lesson_plan)}")
    for item in report["errors"]:
        print(f"- {item['code']}: {item['message']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
