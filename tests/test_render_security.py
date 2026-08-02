from pathlib import Path

from eng_essay_qgen.lesson_plans import load_lesson_plan
from eng_essay_qgen.package_io import load_assessment
from eng_essay_qgen.renderers import render_markdown

FIXTURE = Path(__file__).parent / "fixtures" / "ai_ethics" / "assessment.json"
LESSON_FIXTURE = Path(__file__).parent / "fixtures" / "ai_ethics" / "lesson-plan.json"


def test_student_renderer_is_allowlist_based():
    assessment = load_assessment(FIXTURE)
    assessment["model_answers"].append(
        {
            "id": "malicious",
            "level": "alternative",
            "text": "This secret answer should never appear in a student document.",
        }
    )
    student = render_markdown(assessment, "student")
    assert "secret answer" not in student
    assert "Rubric" not in student
    assert "모범 답안" not in student
    assert "8점" in student


def test_teacher_renderer_contains_private_material():
    assessment = load_assessment(FIXTURE)
    teacher = render_markdown(assessment, "teacher")
    assert "채점 기준" in teacher
    assert assessment["model_answers"][0]["text"] in teacher


def test_teacher_renderer_includes_validated_lesson_plan_sections():
    assessment = load_assessment(FIXTURE)
    assessment["lesson_plan"] = load_lesson_plan(LESSON_FIXTURE)
    teacher = render_markdown(assessment, "teacher")
    assert "교육과정 연계" in teacher
    assert "수업 진행" in teacher
    assert "예상 오개념과 대응" in teacher
    assert "형성평가" in teacher
