import copy
import json
from pathlib import Path

from eng_essay_qgen.package_io import load_assessment
from eng_essay_qgen.validators import validate_assessment, validate_student_security

FIXTURE = Path(__file__).parent / "fixtures" / "ai_ethics" / "assessment.json"


def test_fixture_normalizes_high_school_alias_and_passes_deterministic_checks():
    assessment = load_assessment(FIXTURE)
    assert assessment["metadata"]["grade"] == "고2/3"
    report = validate_assessment(assessment)
    assert report["ok"], json.dumps(report, ensure_ascii=False, indent=2)
    assert report["answers"][0]["word_count"] >= 50
    assert {answer["level"] for answer in assessment["model_answers"]} == {
        "minimum-pass",
        "proficient",
        "alternative",
        "common-error",
    }


def test_word_count_defect_is_reported():
    assessment = load_assessment(FIXTURE)
    broken = copy.deepcopy(assessment)
    broken["model_answers"][0]["text"] = "AI systems can be unfair."
    report = validate_assessment(broken)
    assert not report["ok"]
    assert any(item["code"] == "word_count_out_of_range" for item in report["errors"])


def test_rubric_total_and_condition_link_errors_are_reported():
    assessment = load_assessment(FIXTURE)
    broken = copy.deepcopy(assessment)
    broken["rubric"][0]["points"] = 2
    broken["rubric"][0]["condition_ids"] = ["C1"]
    report = validate_assessment(broken)
    codes = {item["code"] for item in report["errors"]}
    assert "rubric_total_mismatch" in codes
    assert "condition_unlinked" in codes


def test_student_security_ignores_untrusted_answer_fields():
    student = "## 영어 서술형 평가\n\n지문과 조건만 표시합니다.\n\n총점: 8점"
    answer = [{"id": "strong", "text": "This answer must never be rendered to students."}]
    report = validate_student_security(student, model_answers=answer)
    assert report["ok"]


def test_student_security_rejects_rubric_language_and_answer_leak():
    answer_text = "This is a model answer that should remain private."
    student = f"Rubric\n{answer_text}"
    report = validate_student_security(
        student, model_answers=[{"id": "strong", "text": answer_text}]
    )
    assert not report["ok"]
    assert {item["code"] for item in report["errors"]} == {
        "forbidden_student_term",
        "model_answer_leak",
    }
