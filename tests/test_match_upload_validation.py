from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_match_upload_rejects_non_pdf_files():
    response = client.post(
        "/match-upload",
        files={"resume_file": ("resume.txt", b"hello world", "text/plain")},
        data={
            "job_description": "Looking for a Python developer with FastAPI and SQL."
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Only PDF resumes are supported."}
