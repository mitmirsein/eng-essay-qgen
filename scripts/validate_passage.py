#!/usr/bin/env python3
"""Run deterministic passage checks before question generation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from eng_essay_qgen.passage_review import validate_passage  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an English source passage")
    parser.add_argument("passage")
    parser.add_argument("--grade", choices=["중1", "중2", "중3", "고1", "고2", "고3", "고2/3"])
    parser.add_argument(
        "--type", dest="question_type", choices=["type1", "type2", "type3"], default="type1"
    )
    parser.add_argument("--report")
    args = parser.parse_args()
    try:
        report = validate_passage(
            Path(args.passage).read_text(encoding="utf-8"),
            grade=args.grade,
            question_type=args.question_type,
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        Path(args.report).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
