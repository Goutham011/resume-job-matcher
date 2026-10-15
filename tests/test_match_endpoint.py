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
