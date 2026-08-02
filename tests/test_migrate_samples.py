import pytest
from scripts.migrate_samples import SAMPLE_SPECS, migrate_one

from eng_essay_qgen.validators import validate_assessment


@pytest.mark.parametrize("assessment_id", SAMPLE_SPECS)
def test_legacy_sample_can_be_migrated_and_validated(assessment_id):
    assessment = migrate_one(assessment_id)
    report = validate_assessment(assessment)
    assert report["ok"], f"{assessment_id}: {report['errors']}"


def test_migration_repairs_known_answer_lengths_without_touching_legacy_files():
    ai = migrate_one("20260801_123100-type2-ai_ethics")
    assert 50 <= len(ai["model_answers"][0]["text"].split()) <= 70

    differentiated = migrate_one("20260801_133000-diff-climate_change")
    level3 = next(
        item for item in differentiated["differentiated_levels"] if item["id"] == "level3"
    )
    assert 40 <= len(level3["model_answers"][0]["text"].split()) <= 60
