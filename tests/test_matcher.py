from app.services.matcher import match_requirement_coverage, match_resume_to_jd


def test_match_resume_to_jd_returns_expected_fields():
    resume = """
    Python developer with FastAPI, SQL, Docker, and AWS experience.
    Built REST API services and backend systems.
    """

    jd = """
    Looking for a backend engineer with Python, FastAPI, SQL, Docker,
    AWS, and Kubernetes experience.
    """

    result = match_resume_to_jd(resume, jd)

    assert result["matched_skills"] == ["aws", "docker", "fastapi", "python", "sql"]
    assert result["missing_skills"] == ["kubernetes"]
    assert isinstance(result["overall_score"], float)
    assert 0 <= result["overall_score"] <= 100


def test_match_resume_to_jd_includes_requirement_matches_and_dynamic_keywords():
    resume = """
    Python developer with FastAPI experience.
    Built REST API services for payment systems.
    """

    jd = """
    Build REST API services with Python and FastAPI.
    Must have experience designing payment systems.
    """

    result = match_resume_to_jd(resume, jd)

    assert isinstance(result["requirement_matches"], list)
    assert isinstance(result["dynamic_keywords"], list)

    for match in result["requirement_matches"]:
        assert match["status"] in {"covered", "partial", "missing"}
        assert match["kind"] in {"required", "preferred", "general"}


def test_requirement_coverage_marks_matching_line_as_covered():
    from app.services.matcher import get_model

    resume = "Built REST API services with Python and FastAPI for payments."
    jd = "Build REST API services with Python and FastAPI."
    requirements = {"must_have": [], "preferred": []}

    matches = match_requirement_coverage(resume, jd, requirements, get_model())

    assert matches
    assert matches[0]["status"] in {"covered", "partial"}
    assert matches[0]["best_match"] is not None


def test_verbatim_posting_copy_triggers_mirror_warning():
    sentence = "Build scalable data pipelines with Python and Docker for teams. "
    text = sentence * 20

    result = match_resume_to_jd(text, text)

    assert result["score_breakdown"]["resume_chunks"] >= 2
    assert result["score_breakdown"]["content_mirrored"] is True
    assert result["score_breakdown"]["content_similarity"] < 100.0
    assert any(
        "word-for-word" in issue["message"] for issue in result["writing_issues"]
    )
    assert any(
        "copied" in recommendation["title"].lower()
        for recommendation in result["recommendations"]
    )


def test_short_identical_text_is_not_flagged_as_mirrored():
    text = (
        "Kept detailed records for every project milestone and reviewed "
        "them weekly with the group."
    )

    result = match_resume_to_jd(text, text)

    assert result["score_breakdown"]["content_mirrored"] is False


def test_match_without_recognized_skills_uses_content_score_only():
    resume = "Marketing intern with publicity campaign experience on campus."
    jd = "Seeking a motivated individual for a fast-paced role on our team."

    result = match_resume_to_jd(resume, jd)

    assert result["matched_skills"] == []
    assert result["missing_skills"] == []
    assert result["score_breakdown"]["skill_coverage"] is None
    assert result["score_breakdown"]["skill_weight"] == 0
    assert result["score_breakdown"]["content_weight"] == 100
    assert result["overall_score"] == result["score_breakdown"]["content_similarity"]
    assert "wording" in result["explanation"]
