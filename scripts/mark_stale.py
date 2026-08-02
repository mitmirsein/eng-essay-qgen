#!/usr/bin/env python3
"""Propagate selective regeneration staleness through a package manifest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from eng_essay_qgen.teacher_ops import STALE_DEPENDENCIES, mark_stale  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Mark dependent package sections stale")
    parser.add_argument("manifest")
    parser.add_argument("changed_section", choices=sorted(STALE_DEPENDENCIES))
    args = parser.parse_args()
    manifest = mark_stale(args.manifest, args.changed_section)
    print(f"stale: {', '.join(manifest['stale_sections'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
