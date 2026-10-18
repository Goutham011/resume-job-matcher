from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_match_endpoint_returns_expected_shape():
    payload = {
        "resume_text": "Python developer with FastAPI, SQL, and Docker experience.",
        "job_description": (
            "Looking for a Python backend engineer with FastAPI and SQL."
        ),
    }

    response = client.post("/match", json=payload)

    assert response.status_code == 200

    data = response.json()
    assert "overall_score" in data
    assert "matched_skills" in data
    assert "missing_skills" in data
    assert "resume_keywords" in data
    assert "jd_keywords" in data
    assert "explanation" in data
    assert "score_breakdown" in data
    assert "skill_mentions" in data
    assert "writing_issues" in data
    assert "recommendations" in data
    assert "keyword_coverage" in data
    assert "dynamic_keywords" in data
    assert "requirements" in data
    assert "knockout_checks" in data
    assert "requirement_matches" in data
    assert data["ats_audit"] is None
