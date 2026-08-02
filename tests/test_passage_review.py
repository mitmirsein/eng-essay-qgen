import pytest

from eng_essay_qgen.passage_review import validate_passage

VALID_TYPE2 = """(A) People save energy at home because small choices can reduce pollution and
protect rivers.

(B) Communities also restore wetlands, which absorb heavy rain and provide shelter for local
animals."""


def test_passage_review_reports_metrics_and_normalizes_grade():
    report = validate_passage(VALID_TYPE2, grade="고3", question_type="type2")
    assert report["ok"] is True
    assert report["grade"] == "고2/3"
    assert report["metrics"]["word_count"] > 20
    assert report["metrics"]["section_ids"] == ["A", "B"]
    assert report["semantic_review_required"] is True


def test_type2_requires_balanced_a_and_b_sections():
    report = validate_passage(
        "(A) A short section with enough words for review.", question_type="type2"
    )
    assert report["ok"] is False
    assert any(item["code"] == "type2_sections_missing" for item in report["errors"])


def test_abnormal_whitespace_is_a_gate_failure():
    report = validate_passage("A sentence with\tbad spacing.  ", question_type="type1")
    assert report["ok"] is False
    assert any(item["code"] == "abnormal_whitespace" for item in report["errors"])


def test_unknown_grade_and_question_type_are_rejected():
    with pytest.raises(ValueError, match="unsupported grade"):
        validate_passage("A sentence.", grade="고4")
    with pytest.raises(ValueError, match="unsupported question_type"):
        validate_passage("A sentence.", question_type="other")
