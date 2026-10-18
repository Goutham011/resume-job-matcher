import io
import zipfile

from fastapi.testclient import TestClient

from app.main import app
from tests.docx_builder import make_docx
from tests.pdf_builder import make_pdf

client = TestClient(app)

DOCX_MEDIA = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

JD = "Looking for a Python developer with FastAPI and SQL."


def _detail(response):
    return response.json()["detail"]


def test_match_upload_rejects_unsupported_files():
    response = client.post(
        "/match-upload",
        files={"resume_file": ("resume.txt", b"hello world", "text/plain")},
        data={"job_description": JD},
    )

    assert response.status_code == 400
    assert _detail(response)["code"] == "unsupported_file"
    assert "Only PDF and DOCX" in _detail(response)["message"]


def test_match_upload_accepts_docx_files():
    data = make_docx(
        [
            "Goutham Sai",
            "goutham@example.com | +1 555 123 4567",
            "Experience",
            "Built REST API services in Python and FastAPI for three years.",
            "Skills",
            "Python, FastAPI, SQL, Docker",
        ]
    )

    response = client.post(
        "/match-upload",
        files={"resume_file": ("resume.docx", data, DOCX_MEDIA)},
        data={"job_description": JD},
    )

    assert response.status_code == 200

    payload = response.json()
    assert payload["ats_audit"] is not None
    assert "parseability_score" in payload["ats_audit"]


def test_match_upload_rejects_content_that_is_not_a_pdf_or_docx():
    response = client.post(
        "/match-upload",
        files={"resume_file": ("resume.docx", b"not a docx", DOCX_MEDIA)},
        data={"job_description": JD},
    )

    assert response.status_code == 400
    assert _detail(response)["code"] == "unsupported_file"


def test_match_upload_rejects_content_mismatched_with_extension():
    pdf_bytes = make_pdf([(50, 60, "Resume body text for testing.")])

    response = client.post(
        "/match-upload",
        files={"resume_file": ("resume.docx", pdf_bytes, DOCX_MEDIA)},
        data={"job_description": JD},
    )

    assert response.status_code == 400
    assert _detail(response)["code"] == "unsupported_file"
    assert "doesn't match" in _detail(response)["message"]


def test_match_upload_rejects_files_over_size_limit():
    big = b"%PDF-1.4\n" + b"0" * 5_100_000

    response = client.post(
        "/match-upload",
        files={"resume_file": ("resume.pdf", big, "application/pdf")},
        data={"job_description": JD},
    )

    assert response.status_code == 413
    assert _detail(response)["code"] == "file_too_large"


def test_match_upload_rejects_zip_bombs():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"0" * 51_000_000)

    response = client.post(
        "/match-upload",
        files={"resume_file": ("resume.docx", buffer.getvalue(), DOCX_MEDIA)},
        data={"job_description": JD},
    )

    assert response.status_code == 413
    assert _detail(response)["code"] == "file_too_large"


def test_match_upload_rejects_zip_without_word_document():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")

    response = client.post(
        "/match-upload",
        files={"resume_file": ("resume.docx", buffer.getvalue(), DOCX_MEDIA)},
        data={"job_description": JD},
    )

    assert response.status_code == 400
    assert _detail(response)["code"] == "unsupported_file"


def test_scanned_pdf_returns_422_with_audit_payload():
    response = client.post(
        "/match-upload",
        files={"resume_file": ("resume.pdf", make_pdf([]), "application/pdf")},
        data={"job_description": JD},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["code"] == "unreadable_document"
    assert "Could not read any text" in body["detail"]["message"]

    audit = body["ats_audit"]
    assert audit["parseability_score"] <= 20
    assert audit["issues"]
    assert any("No selectable text" in issue["message"] for issue in audit["issues"])


def test_empty_valid_docx_returns_422_with_audit_payload():
    response = client.post(
        "/match-upload",
        files={"resume_file": ("resume.docx", make_docx([]), DOCX_MEDIA)},
        data={"job_description": JD},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["code"] == "unreadable_document"
    assert body["ats_audit"]["parseability_score"] <= 20
