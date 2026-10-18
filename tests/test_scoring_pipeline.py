import pytest

from app.errors import AppError
from app.services.chunking import MAX_INPUT_CHUNKS, chunk_text
from app.services.matcher import match_resume_to_jd
from tests.fake_model import FakeModel


def test_long_resume_is_chunked_not_truncated():
    sentence = "Built scalable data pipelines and dashboards for the team. "
    resume = sentence * 120
    jd = "We need someone to build scalable data pipelines and dashboards. " * 40

    result = match_resume_to_jd(resume, jd)

    breakdown = result["score_breakdown"]
    assert breakdown["resume_chunks"] > 1
    assert breakdown["jd_chunks"] > 1
    assert breakdown["chunk_max_tokens"] == 256
    assert 0 <= result["overall_score"] <= 100


def test_chunk_text_rejects_oversized_documents():
    text = "Built platforms for teams with care. " * 45_000

    with pytest.raises(AppError) as excinfo:
        chunk_text(FakeModel(), text)

    assert excinfo.value.status_code == 422
    assert excinfo.value.code == "invalid_input"
    assert MAX_INPUT_CHUNKS < 45_000


def test_identical_text_scores_high():
    text = (
        "Kept detailed records for every project milestone and reviewed "
        "them weekly with the group."
    )

    result = match_resume_to_jd(text, text)

    assert result["score_breakdown"]["content_similarity"] == 100.0
    assert result["overall_score"] == 100.0


def test_scores_stay_within_bounds():
    text = "Python FastAPI SQL Docker AWS " * 30

    result = match_resume_to_jd(text, text)

    assert 0 <= result["overall_score"] <= 100
    assert 0 <= result["score_breakdown"]["content_similarity"] <= 100
    assert result["score_breakdown"]["skill_coverage"] == 100.0


def test_soft_skills_count_half_weight_in_coverage():
    result = match_resume_to_jd(
        "Python developer with strong communication skills.",
        "Python developer with strong communication skills and leadership ability.",
    )

    assert result["matched_skills"] == ["communication", "python"]
    assert result["missing_skills"] == ["leadership"]
    coverage = result["score_breakdown"]["skill_coverage"]
    assert coverage == pytest.approx(75.0, abs=0.01)


def test_keyword_coverage_marks_soft_skills():
    result = match_resume_to_jd(
        "Great communication with every teammate on my team.",
        "Strong communication and teamwork required.",
    )

    kinds = {item["skill"]: item["kind"] for item in result["keyword_coverage"]}
    assert kinds.get("communication") == "soft"
    assert kinds.get("teamwork") == "soft"
