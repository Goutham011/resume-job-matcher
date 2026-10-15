from app.services.matcher import match_resume_to_jd


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
