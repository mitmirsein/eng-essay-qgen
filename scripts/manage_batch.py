#!/usr/bin/env python3
"""Initialize and operate a human-reviewed answer-sheet batch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from eng_essay_qgen.teacher_ops import (  # noqa: E402
    BATCH_STATES,
    eligible_for_grading,
    init_batch,
    transition_batch_item,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage HITL-reviewed answer batches")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create a pending-extraction batch")
    init_parser.add_argument("batch_id")
    init_parser.add_argument("--output-root", required=True)
    init_parser.add_argument("--source", action="append", default=[])
    init_parser.add_argument("--retain-handwriting-images", action="store_true")
    init_parser.add_argument("--resume", action="store_true")

    transition_parser = subparsers.add_parser("transition", help="record an HITL state change")
    transition_parser.add_argument("batch_dir")
    transition_parser.add_argument("anonymous_id")
    transition_parser.add_argument("status", choices=sorted(BATCH_STATES))
    transition_parser.add_argument("--transcript")
    transition_parser.add_argument("--uncertain-span", action="append", default=[])
    transition_parser.add_argument("--note", default="")

    eligible_parser = subparsers.add_parser(
        "eligible", help="list items eligible for deterministic grading"
    )
    eligible_parser.add_argument("batch_dir")

    args = parser.parse_args()
    try:
        if args.command == "init":
            if not args.source and not args.resume:
                parser.error("init requires at least one --source unless --resume is used")
            batch_dir = init_batch(
                args.batch_id,
                args.source,
                args.output_root,
                retain_handwriting_images=args.retain_handwriting_images,
                resume=args.resume,
            )
            print(batch_dir)
            return 0
        if args.command == "transition":
            item = transition_batch_item(
                args.batch_dir,
                args.anonymous_id,
                args.status,
                transcript=args.transcript,
                uncertain_spans=args.uncertain_span,
                note=args.note,
            )
            print(json.dumps(item, ensure_ascii=False, indent=2))
            return 0
        if args.command == "eligible":
            print(json.dumps(eligible_for_grading(args.batch_dir), ensure_ascii=False, indent=2))
            return 0
    except (FileExistsError, KeyError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
