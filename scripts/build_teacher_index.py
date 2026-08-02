#!/usr/bin/env python3
"""Build a Markdown or HTML artifact index from package manifests."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from eng_essay_qgen.teacher_ops import write_teacher_index  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a teacher artifact index")
    parser.add_argument("root", help="directory containing package manifests")
    parser.add_argument("--output", required=True)
    parser.add_argument("--format", choices=["markdown", "html"], default="markdown")
    args = parser.parse_args()
    write_teacher_index(args.root, args.output, format=args.format)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
