from app.services.extractor import extract_skills


def test_extract_skills_finds_expected_keywords():
    text = """
    Experienced Python developer with FastAPI, SQL, Docker, GitHub,
    and AWS experience. Built REST API services.
    """

    skills = extract_skills(text)

    assert "python" in skills
    assert "fastapi" in skills
    assert "sql" in skills
    assert "docker" in skills
    assert "aws" in skills
    assert "github" in skills
    assert "rest api" in skills
