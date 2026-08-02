import json
from pathlib import Path

import pytest

from eng_essay_qgen.manifests import build_manifest
from eng_essay_qgen.teacher_ops import (
    build_teacher_index,
    eligible_for_grading,
    init_batch,
    load_teacher_profile,
    mark_stale,
    merge_profile,
    summarize_class,
    transition_batch_item,
    write_class_summary,
    write_teacher_index,
)


def test_teacher_profile_normalizes_grade_and_accepts_overrides():
    profile = load_teacher_profile()
    merged = merge_profile(
        profile,
        {"default_grade": "고2", "instruction_language_ratio": {"korean": 60, "english": 40}},
    )
    assert profile["default_grade"] == "중3"
    assert merged["default_grade"] == "고2/3"
    assert merged["instruction_language_ratio"] == {"korean": 60, "english": 40}


def test_manifest_records_applied_profile_without_school_name(tmp_path: Path):
    artifact = tmp_path / "student.md"
    artifact.write_text("student", encoding="utf-8")
    profile = merge_profile(load_teacher_profile(), {"default_grade": "고2"})
    manifest = build_manifest(
        assessment_id="assessment-1",
        schema_version="1.0.0",
        package_dir=tmp_path,
        output_paths=[artifact],
        teacher_profile=profile,
    )
    assert manifest["teacher_profile"]["default_grade"] == "고2/3"
    assert "school_name" not in manifest["teacher_profile"]


def test_teacher_index_reads_manifests_and_writes_views(tmp_path: Path):
    package_dir = tmp_path / "assessment"
    package_dir.mkdir()
    manifest = {
        "schema_version": "1.0.0",
        "assessment_id": "assessment-1",
        "generated_at": "2026-08-02T00:00:00+00:00",
        "assessment_metadata": {
            "title": "평가 1",
            "topic": "기후 변화",
            "grade": "중3",
            "question_type": "type2",
        },
        "qa_status": "pass",
        "outputs": [{"path": "student.md"}, {"path": "teacher.md"}],
    }
    (package_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    index = build_teacher_index(tmp_path)
    assert len(index["items"]) == 1
    assert index["items"][0]["assessment_id"] == "assessment-1"
    assert index["items"][0]["topic"] == "기후 변화"
    assert index["items"][0]["regeneration_required"] is False
    markdown_path = write_teacher_index(tmp_path, tmp_path / "index.md")
    html_path = write_teacher_index(tmp_path, tmp_path / "index.html", format="html")
    assert "assessment-1" in markdown_path.read_text(encoding="utf-8")
    assert "assessment-1" in html_path.read_text(encoding="utf-8")


def test_batch_requires_hitl_before_grading(tmp_path: Path):
    source_a = tmp_path / "answer-a.png"
    source_b = tmp_path / "answer-b.png"
    source_a.write_bytes(b"fixture-a")
    source_b.write_bytes(b"fixture-b")
    batch_dir = init_batch("batch-1", [source_a, source_b], tmp_path / "batches")
    assert init_batch("batch-1", [], tmp_path / "batches", resume=True) == batch_dir

    batch_manifest = json.loads((batch_dir / "batch-manifest.json").read_text(encoding="utf-8"))
    approvals = json.loads((batch_dir / "approvals.json").read_text(encoding="utf-8"))
    source_map = json.loads((batch_dir / "source_map.local.json").read_text(encoding="utf-8"))
    assert batch_manifest["uses_anonymous_student_ids"] is True
    assert all("source_path" not in item for item in approvals["items"])
    assert len(source_map) == 2
    assert eligible_for_grading(batch_dir) == []

    anonymous_id = approvals["items"][0]["anonymous_id"]
    transition_batch_item(
        batch_dir,
        anonymous_id,
        "pending-review",
        transcript="A reviewed transcript.",
        uncertain_spans=["word 3"],
    )
    transcription_csv = (batch_dir / "transcriptions.csv").read_text(encoding="utf-8")
    assert "pending-review" in transcription_csv
    assert "reviewed transcript" in transcription_csv
    transition_batch_item(batch_dir, anonymous_id, "corrected", note="HITL correction")
    transition_batch_item(batch_dir, anonymous_id, "approved")
    assert eligible_for_grading(batch_dir)[0]["anonymous_id"] == anonymous_id
    with pytest.raises(ValueError, match="invalid batch transition"):
        transition_batch_item(batch_dir, anonymous_id, "pending-review")


def test_class_summary_is_anonymous_and_identifies_reteach_conditions(tmp_path: Path):
    rows = [
        {
            "anonymous_id": "stu-a",
            "score": 8,
            "total_points": 8,
            "conditions": {"C1": True, "C2": True},
            "error_tags": ["grammar"],
        },
        {
            "anonymous_id": "stu-b",
            "score": 4,
            "total_points": 8,
            "conditions": {"C1": True, "C2": False},
            "error_tags": ["grammar", "content"],
        },
        {
            "anonymous_id": "stu-c",
            "score": 2,
            "total_points": 8,
            "conditions": {"C1": False, "C2": False},
            "error_tags": "content",
        },
    ]
    summary = summarize_class(rows)
    assert summary["student_count"] == 3
    assert summary["average_score"] == pytest.approx(14 / 3)
    assert summary["condition_attainment"]["C2"] == pytest.approx(1 / 3)
    assert summary["reteach_conditions"] == ["C1", "C2"]
    assert [item["condition_id"] for item in summary["reteach_recommendations"]] == ["C1", "C2"]
    assert summary["strong_answer_candidates"] == ["stu-a"]
    assert summary["error_patterns"] == {"grammar": 2, "content": 2}
    assert summary["privacy"]["student_names_included"] is False
    json_path, csv_path = write_class_summary(rows, tmp_path / "class-insights")
    assert json_path.exists()
    assert csv_path.exists()
    summary_text = json_path.read_text(encoding="utf-8")
    assert "학생명" not in summary_text
    assert "stu-a" in summary_text


def test_mark_stale_records_selective_dependencies(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"assessment_id": "assessment-1", "stale_sections": []}),
        encoding="utf-8",
    )
    manifest = mark_stale(manifest_path, "passage")
    assert "task_conditions" in manifest["stale_sections"]
    assert "teacher_pdf" in manifest["stale_sections"]
    assert manifest["last_modified"]
    assert manifest["events"][0]["changed_section"] == "passage"
