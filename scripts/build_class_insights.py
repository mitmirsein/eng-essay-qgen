#!/usr/bin/env python3
"""Aggregate anonymized grading rows into class-level read-only insights."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from eng_essay_qgen.teacher_ops import write_class_summary  # noqa: E402


def _read_rows(path: Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else data.get("rows", [])
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build anonymous class insights")
    parser.add_argument("rows")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    json_path, csv_path = write_class_summary(_read_rows(Path(args.rows)), args.output)
    print(f"{json_path}\n{csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
