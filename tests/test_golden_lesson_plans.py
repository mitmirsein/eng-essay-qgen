import json
from pathlib import Path

from eng_essay_qgen.lesson_plans import load_lesson_plan, validate_lesson_plan

GOLDEN_ROOT = Path(__file__).parent / "golden"


def test_type_specific_golden_lesson_plans_pass_deterministic_checks():
    paths = sorted(GOLDEN_ROOT.glob("type*.json"))
    assert {path.name for path in paths} == {
        "type1-snow-white.json",
        "type2-ai-ethics.json",
        "type3-smartphone.json",
    }
    for path in paths:
        report = validate_lesson_plan(load_lesson_plan(path))
        assert report["ok"], f"{path}: {json.dumps(report, ensure_ascii=False)}"
