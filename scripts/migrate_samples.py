#!/usr/bin/env python3
"""Copy-based migration of the six legacy samples into private packages.

The legacy Markdown files remain untouched. The output directory is explicit so a
caller can point it at /tmp for a dry run or at output/lesson-plans/_packages when
the generated packages are ready to be adopted.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from eng_essay_qgen.package_io import AssessmentIOError, save_assessment  # noqa: E402
from eng_essay_qgen.text_metrics import count_words  # noqa: E402

SAMPLE_SPECS = {
    "20260801_120100-type1-snow_white": {
        "question": "output/essay-questions/20260801_120100-type1-snow_white.md",
        "lesson": "output/lesson-plans/20260801_120200-type1-snow_white_lesson.md",
        "passage": "passages/20260801_120000-type1-snow_white.txt",
        "grade": "중1",
        "question_type": "type1",
        "topic": "백설공주와 거울",
    },
    "20260801_121100-type2-white_lie": {
        "question": "output/essay-questions/20260801_121100-type2-white_lie.md",
        "lesson": "output/lesson-plans/20260801_121200-type2-white_lie_lesson.md",
        "passage": "passages/20260801_121000-type2-white_lie.txt",
        "grade": "중3",
        "question_type": "type2",
        "topic": "하얀 거짓말",
    },
    "20260801_122100-type2-climate_change": {
        "question": "output/essay-questions/20260801_122100-type2-climate_change.md",
        "lesson": "output/lesson-plans/20260801_122200-type2-climate_change_lesson.md",
        "passage": "passages/20260801_122000-type2-climate_change.txt",
        "grade": "중3",
        "question_type": "type2",
        "topic": "기후 변화",
    },
    "20260801_123100-type2-ai_ethics": {
        "question": "output/essay-questions/20260801_123100-type2-ai_ethics.md",
        "lesson": "output/lesson-plans/20260801_123200-type2-ai_ethics_lesson.md",
        "passage": "passages/20260801_123000-type2-ai_ethics.txt",
        "grade": "고1",
        "question_type": "type2",
        "topic": "인공지능과 윤리",
    },
    "20260801_124100-type3-smartphone": {
        "question": "output/essay-questions/20260801_124100-type3-smartphone.md",
        "lesson": "output/lesson-plans/20260801_124200-type3-smartphone_lesson.md",
        "passage": "passages/20260801_124000-type3-smartphone.txt",
        "grade": "중1",
        "question_type": "type3",
        "topic": "스마트폰 사용 습관",
    },
    "20260801_133000-diff-climate_change": {
        "question": "output/essay-questions/20260801_133000-diff-climate_change.md",
        "lesson": "output/lesson-plans/20260801_133000-diff-climate_change_lesson.md",
        "passage": "passages/20260801_122000-type2-climate_change.txt",
        "grade": "중3",
        "question_type": "differentiated",
        "topic": "기후 변화 수준별 쓰기",
    },
}

# The migration corrects the two known legacy answer defects in the private
# source of truth. It never changes the legacy Markdown files.
ANSWER_OVERRIDES = {
    "20260801_123100-type2-ai_ethics": {
        "strong": (
            "Artificial intelligence offers useful services, yet biased "
            "algorithms can treat communities unfairly. Systems which "
            "gather personal information may also weaken privacy. "
            "Governments should create firm rules that protect individuals "
            "before these tools become widespread. Careful human oversight "
            "can reduce unfair decisions, while responsible design helps people "
            "keep control over their data and use technology safely."
        )
    },
    "20260801_133000-diff-climate_change": {
        "level1": "Polar bears lose their homes because the ice melts fast.",
        "level3": (
            "Facing hotter summers and stronger floods, communities and "
            "wildlife are suffering from climate change. Polar bears are "
            "losing habitats as ice disappears, while cities face dangerous "
            "weather. We should save energy and reduce pollution to protect "
            "people and animals, making environmental "
            "action an urgent shared responsibility for everyone."
        ),
    },
}


def _read(relative: str) -> str:
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def _passage_sections(text: str) -> list[dict[str, str]]:
    sections = []
    matches = list(re.finditer(r"(?:^|\n)\(([A-Z])\)\s*", text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section_text = text[match.end() : end].strip()
        sections.append({"id": match.group(1), "text": section_text})
    return sections


def _extract_passage(question_text: str) -> str:
    marker = "> [!NOTE] 지문 (Reading Passage)"
    if marker not in question_text:
        raise ValueError("reading passage marker not found")
    block = question_text.split(marker, 1)[1].split("\n###", 1)[0]
    lines = []
    for line in block.splitlines():
        if line.startswith("> "):
            lines.append(line[2:])
        elif line == ">":
            lines.append("")
    return "\n".join(lines).strip()


def _extract_instruction(question_text: str) -> str:
    for line in question_text.splitlines():
        match = re.match(r"^\*\*(.+?)\*\*$", line.strip())
        if match:
            return re.sub(r"\s*\[\d+(?:\.\d+)?점(?:, [^]]+)?\]\s*$", "", match.group(1)).strip()
    raise ValueError("task instruction not found")


def _level_blocks(question_text: str) -> list[dict[str, Any]]:
    matches = list(re.finditer(r"^### \[Level (\d)\].*?$", question_text, flags=re.MULTILINE))
    blocks = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(question_text)
        block = question_text[match.end() : end]
        instruction = next(
            (
                line.strip().strip("*").strip()
                for line in block.splitlines()
                if line.strip().startswith("**")
            ),
            "",
        )
        condition_text = block.split("#### 📌 <조건>", 1)[-1].split("---", 1)[0]
        conditions = [
            match.group(1).strip()
            for match in re.finditer(r"^\d+\.\s+(.+)$", condition_text, re.MULTILINE)
        ]
        blocks.append(
            {"number": match.group(1), "instruction": instruction, "conditions": conditions}
        )
    return blocks


def _extract_conditions(question_text: str) -> list[str]:
    condition_text = question_text.split("### 📌 <조건>", 1)[-1]
    condition_text = condition_text.split("---", 1)[0]
    return [
        match.group(1).strip()
        for match in re.finditer(r"^\d+\.\s+(.+)$", condition_text, re.MULTILINE)
    ]


def _condition_validation(text: str) -> tuple[str, str, dict[str, Any]]:
    length = re.search(r"(\d+)\s*[~\-]\s*(\d+)\s*단어", text)
    if length:
        return "length", "word_count", {"min": int(length.group(1)), "max": int(length.group(2))}
    if "Dear Jimin" in text or "From, Minho" in text:
        return "format", "format", {"starts_with": "Dear Jimin,", "ends_with": "From, Minho"}
    quoted = re.findall(r'"([^"\n]+)"', text)
    if quoted:
        return "citation", "literal_required", {"values": quoted}
    words = re.findall(r"\(([^()]+)\)", text)
    if words and "," in words[0] and "모두" in text:
        values = [value.strip() for value in words[0].split(",") if value.strip()]
        return "grammar", "literal_required", {"values": values}
    if "5단어" in text or "5단어 이상" in text:
        return "restriction", "ngram_limit", {"n": 5}
    if "접속사" in text:
        return "grammar", "surface_pattern", {"pattern": r"\b(?:when|because|so)\b", "min_count": 1}
    if "분사구문" in text or "현재분사" in text:
        return "grammar", "surface_pattern", {"pattern": r"\b[A-Za-z]+ing\b", "min_count": 1}
    if "현재완료" in text:
        return (
            "grammar",
            "surface_pattern",
            {"pattern": r"\b(?:has|have)\s+[A-Za-z]+(?:ed|en|lost|gone)\b", "min_count": 1},
        )
    if "관계대명사" in text:
        return "grammar", "surface_pattern", {"pattern": r"\b(?:who|which|that)\b", "min_count": 2}
    if "조동사" in text and "to부정사" in text:
        return (
            "grammar",
            "surface_pattern",
            {
                "pattern": r"(?s)(?=.*\b(?:will|can)\b)(?=.*\bto\s+[A-Za-z]+\b)",
                "min_count": 1,
            },
        )
    return "content", "semantic", {}


def _conditions_from_text(texts: list[str], prefix: str = "C") -> list[dict[str, Any]]:
    conditions = []
    for index, text in enumerate(texts, start=1):
        category, kind, params = _condition_validation(text)
        conditions.append(
            {
                "id": f"{prefix}{index}",
                "category": category,
                "text_ko": text,
                "validation": {
                    "kind": kind,
                    "check_mode": "semantic" if kind == "semantic" else "deterministic",
                    "params": params,
                },
            }
        )
    return conditions


def _extract_rubric_lines(lesson_text: str) -> list[tuple[float, str, str]]:
    result = []
    for line in lesson_text.splitlines():
        match = re.match(r"^-\s+\*\*\[(\d+(?:\.\d+)?)점\]\s*(.*?)\*\*:\s*(.+)$", line.strip())
        if match:
            result.append((float(match.group(1)), match.group(2), match.group(3).strip()))
    return result


def _rubric_from_lines(
    lines: list[tuple[float, str, str]],
    prefix: str,
    condition_count: int,
    condition_prefix: str = "C",
) -> list[dict[str, Any]]:
    rubric = []
    for index, (points, label, description) in enumerate(lines, start=1):
        reference_groups = re.findall(r"조건\s*([0-9]+(?:\s*[,및]\s*[0-9]+)*)", label)
        references = [
            int(value) for group in reference_groups for value in re.findall(r"\d+", group)
        ]
        if not references:
            references = [min(index, condition_count)]
        references = [min(value, condition_count) for value in references]
        rubric.append(
            {
                "id": f"{prefix}{index}",
                "condition_ids": [f"{condition_prefix}{value}" for value in references],
                "points": points,
                "full_credit_ko": description,
                "partial_credit_ko": "교사 정책에 따라 부분점수를 적용한다.",
            }
        )
    return rubric


def _answer_block(lesson_text: str) -> str:
    match = re.search(r"^### 2\..*?$", lesson_text, flags=re.MULTILINE)
    if not match:
        match = re.search(r"^### .*모범 답안.*?$", lesson_text, flags=re.MULTILINE)
    if not match:
        raise ValueError("model answer section not found")
    end_match = re.search(r"^### 3\.|^### 📊", lesson_text[match.end() :], flags=re.MULTILINE)
    block = lesson_text[
        match.end() : match.end() + end_match.start() if end_match else len(lesson_text)
    ]
    lines = []
    for line in block.splitlines():
        value = line.strip()
        if not value or value.startswith("*(※") or value.startswith("- **"):
            continue
        value = re.sub(r"\s*\(\d+\s*words?\)\s*$", "", value)
        if value.startswith("(") and value.endswith(")"):
            continue
        lines.append(value)
    return "\n".join(lines).strip()


def _standard_answers(assessment_id: str, lesson_text: str) -> list[dict[str, str]]:
    override = ANSWER_OVERRIDES.get(assessment_id, {}).get("strong")
    text = override or _answer_block(lesson_text)
    return [{"id": "strong", "level": "proficient", "text": text}]


def _differentiated_answers(assessment_id: str, lesson_text: str) -> dict[str, str]:
    answers: dict[str, str] = {}
    for match in re.finditer(
        r"^-\s+\*\*\[Level\s+(\d)\]\*\*:\s*(.+)$", lesson_text, flags=re.MULTILINE
    ):
        text = re.sub(r"\s*\(\d+\s*words?\)\s*$", "", match.group(2).strip())
        answers[f"level{match.group(1)}"] = text
    answers.update(ANSWER_OVERRIDES.get(assessment_id, {}))
    return answers


def migrate_one(assessment_id: str) -> dict[str, Any]:
    spec = SAMPLE_SPECS[assessment_id]
    question_text = _read(spec["question"])
    lesson_text = _read(spec["lesson"])
    passage = _read(spec["passage"]).strip()
    created_at = datetime.now(UTC).isoformat()
    base = {
        "schema_version": "1.0.0",
        "assessment_id": assessment_id,
        "metadata": {
            "title": "영어 서술형 평가",
            "topic": spec["topic"],
            "grade": spec["grade"],
            "question_type": spec["question_type"],
            "total_points": 8,
            "created_at": created_at,
            "source_passage_path": spec["passage"],
        },
        "passage": {
            "genre": "narrative"
            if spec["question_type"] == "type1"
            else "practical"
            if spec["question_type"] == "type3"
            else "expository",
            "text": passage,
            "sections": _passage_sections(passage),
        },
        "task": {
            "instruction_ko": _extract_instruction(question_text),
            "audience": "teacher-assigned",
            "purpose": "synthesis" if spec["question_type"] == "type2" else "guided-writing",
            "response_format": "letter" if spec["question_type"] == "type3" else "one-paragraph",
        },
        "language_policy": {
            "error_penalty": 0.5,
            "max_language_penalty": 2.0,
            "repeated_error_policy": "same-root-once",
            "double_penalty_allowed": False,
        },
    }
    if spec["question_type"] != "differentiated":
        conditions = _conditions_from_text(_extract_conditions(question_text))
        rubric_lines = _extract_rubric_lines(lesson_text)
        rubric = _rubric_from_lines(rubric_lines, "R", len(conditions))
        if sum(item["points"] for item in rubric) != 8:
            raise ValueError(f"{assessment_id}: migrated rubric does not total 8")
        base["conditions"] = conditions
        base["rubric"] = rubric
        base["model_answers"] = _standard_answers(assessment_id, lesson_text)
    else:
        base["conditions"] = []
        base["rubric"] = []
        base["model_answers"] = []
        levels = []
        question_levels = _level_blocks(question_text)
        answers = _differentiated_answers(assessment_id, lesson_text)
        lesson_rubric = _extract_rubric_lines(lesson_text)
        for level in question_levels:
            level_id = f"level{level['number']}"
            conditions = _conditions_from_text(level["conditions"], prefix="C")
            level_lines = []
            marker = f"#### [Level {level['number']}]"
            if marker in lesson_text:
                level_block = lesson_text.split(marker, 1)[1].split("#### [Level", 1)[0]
                level_lines = _extract_rubric_lines(level_block)
            if not level_lines:
                level_lines = lesson_rubric
            rubric = _rubric_from_lines(level_lines, "R", len(conditions))
            level_answer = answers.get(level_id)
            if not level_answer:
                raise ValueError(f"{assessment_id}: missing answer for {level_id}")
            levels.append(
                {
                    "id": level_id,
                    "label": f"Level {level['number']}",
                    "instruction_ko": level["instruction"],
                    "conditions": conditions,
                    "rubric": rubric,
                    "model_answers": [
                        {"id": "strong", "level": "proficient", "text": level_answer}
                    ],
                }
            )
        base["differentiated_levels"] = levels
    return base


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate legacy essay samples into assessment packages"
    )
    parser.add_argument(
        "--output", required=True, help="package root, e.g. /tmp/essay-qgen-migration"
    )
    parser.add_argument("--sample", choices=[*SAMPLE_SPECS, "all"], default="all")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    output_root = Path(args.output)
    selected = list(SAMPLE_SPECS) if args.sample == "all" else [args.sample]
    try:
        for assessment_id in selected:
            assessment = migrate_one(assessment_id)
            target = output_root / assessment_id / "assessment.json"
            save_assessment(assessment, target, overwrite=args.overwrite, package_root=output_root)
            passage_words = count_words(assessment["passage"]["text"])
            print(f"migrated: {assessment_id} ({passage_words} passage words)")
    except (AssessmentIOError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
