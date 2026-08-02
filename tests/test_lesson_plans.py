import copy
import json
from pathlib import Path

from eng_essay_qgen.lesson_plans import load_lesson_plan, validate_lesson_plan
from eng_essay_qgen.package_io import load_assessment

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "ai_ethics"


def test_lesson_plan_fixture_passes_cross_document_checks():
    plan = load_lesson_plan(FIXTURE_ROOT / "lesson-plan.json")
    assessment = load_assessment(FIXTURE_ROOT / "assessment.json")
    report = validate_lesson_plan(plan, assessment=assessment)
    assert report["ok"], json.dumps(report, ensure_ascii=False, indent=2)


def test_lesson_plan_duration_and_curriculum_errors_are_deterministic():
    plan = load_lesson_plan(FIXTURE_ROOT / "lesson-plan.json")
    broken = copy.deepcopy(plan)
    broken["sequence"][0]["minutes"] = 6
    broken["standards"][0]["code"] = "not-a-real-code"
    report = validate_lesson_plan(broken)
    codes = {item["code"] for item in report["errors"]}
    assert {"duration_mismatch", "curriculum_code_unknown"} <= codes


def test_lesson_plan_rejects_missing_condition_plan():
    plan = load_lesson_plan(FIXTURE_ROOT / "lesson-plan.json")
    assessment = load_assessment(FIXTURE_ROOT / "assessment.json")
    broken = copy.deepcopy(plan)
    broken["answer_planning"]["condition_to_sentence_map"] = ["C1만 다룬다."]
    report = validate_lesson_plan(broken, assessment=assessment)
    assert any(item["code"] == "condition_not_planned" for item in report["errors"])
