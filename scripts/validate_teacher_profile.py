#!/usr/bin/env python3
"""Validate and normalize a teacher profile YAML file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from eng_essay_qgen.teacher_ops import load_teacher_profile  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate teacher profile")
    parser.add_argument("profile", nargs="?", help="YAML path; defaults to configured profile")
    args = parser.parse_args()
    try:
        profile = load_teacher_profile(args.profile)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(profile, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
