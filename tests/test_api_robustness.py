import io
import threading

from fastapi.testclient import TestClient
from pypdf import PdfWriter

import app.main as main_module
import app.middleware as middleware_module
from app.main import app
from app.services.model_manager import ModelUnavailableError, model_manager

client = TestClient(app)

PAYLOAD = {
    "resume_text": "Python developer with FastAPI, SQL, and Docker experience.",
    "job_description": "Looking for a Python backend engineer with FastAPI and SQL.",
}


def test_match_endpoint_rejects_whitespace_only_text():
    response = client.post(
        "/match",
        json={"resume_text": " " * 40, "job_description": "\n" * 40},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_input"


def test_match_endpoint_sets_request_id_header():
    response = client.post("/match", json=PAYLOAD)

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]


def test_error_responses_include_code_and_request_id():
    response = client.post(
        "/match",
        json={"resume_text": "short", "job_description": "short"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["code"] == "invalid_input"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_oversized_payload_returns_413():
    response = client.post(
        "/match",
        json={
            "resume_text": "a" * 1_600_000,
            "job_description": "Python backend role " * 10,
        },
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "payload_too_large"
    assert response.headers["X-Request-ID"]


def test_resume_text_over_char_cap_returns_422():
    response = client.post(
        "/match",
        json={
            "resume_text": "a" * 200_001,
            "job_description": "Python backend role " * 10,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_input"


def test_pdf_with_too_many_pages_returns_413():
    writer = PdfWriter()
    for _ in range(41):
        writer.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    writer.write(buffer)

    response = client.post(
        "/match-upload",
        files={
            "resume_file": ("resume.pdf", buffer.getvalue(), "application/pdf"),
        },
        data={"job_description": "Python backend role with SQL and Docker work."},
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "file_too_large"


def test_validation_message_names_the_invalid_field():
    short_resume = client.post(
        "/match",
        json={"resume_text": "too short", "job_description": "Python " * 6},
    )
    assert "resume" in short_resume.json()["detail"]["message"].lower()

    short_jd = client.post(
        "/match",
        json={"resume_text": "Python " * 6, "job_description": "too short"},
    )
    assert "job description" in short_jd.json()["detail"]["message"].lower()


def test_rate_limited_requests_return_429(monkeypatch):
    monkeypatch.setattr(
        middleware_module, "is_rate_limited", lambda *args, **kwargs: True
    )

    response = client.post("/match", json=PAYLOAD)

    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "rate_limited"
    assert response.headers["Retry-After"]


def test_rate_limiter_allows_requests_within_limit():
    middleware_module.reset_rate_limits()

    assert not middleware_module.is_rate_limited(
        "127.0.0.1", max_requests=2, window_seconds=60
    )
    assert not middleware_module.is_rate_limited(
        "127.0.0.1", max_requests=2, window_seconds=60
    )
    assert middleware_module.is_rate_limited(
        "127.0.0.1", max_requests=2, window_seconds=60
    )
    assert not middleware_module.is_rate_limited(
        "127.0.0.2", max_requests=2, window_seconds=60
    )


def test_match_endpoint_offloads_work_to_threadpool(monkeypatch):
    calls = []
    original = main_module.run_in_threadpool
    running_loop_thread = threading.get_ident()

    async def spy(func, *args, **kwargs):
        calls.append(True)
        return await original(func, *args, **kwargs)

    monkeypatch.setattr(main_module, "run_in_threadpool", spy)

    response = client.post("/match", json=PAYLOAD)

    assert response.status_code == 200
    assert calls
    assert threading.get_ident() == running_loop_thread


def test_match_endpoint_runs_matcher_off_the_main_thread(monkeypatch):
    original = main_module.match_resume_to_jd
    seen = {}

    def spy(resume_text, jd_text):
        seen["thread"] = threading.current_thread()
        return original(resume_text, jd_text)

    monkeypatch.setattr(main_module, "match_resume_to_jd", spy)

    response = client.post("/match", json=PAYLOAD)

    assert response.status_code == 200
    assert seen["thread"] is not threading.current_thread()


def test_healthz_always_ok():
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readyz_ready_when_model_is_available():
    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_readyz_503_when_model_is_unavailable(monkeypatch):
    def boom():
        raise ModelUnavailableError("model missing")

    monkeypatch.setattr(model_manager, "get_model", boom)

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "model_unavailable"


def test_match_returns_503_when_model_is_unavailable(monkeypatch):
    def boom():
        raise ModelUnavailableError("model missing")

    monkeypatch.setattr(model_manager, "get_model", boom)

    response = client.post("/match", json=PAYLOAD)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "model_unavailable"


def test_unexpected_errors_return_internal_error_contract(monkeypatch):
    def boom(resume_text, jd_text):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(main_module, "match_resume_to_jd", boom)

    response = client.post("/match", json=PAYLOAD)

    assert response.status_code == 500
    body = response.json()
    assert body["detail"]["code"] == "internal_error"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_tailor_docx_is_visible_in_openapi():
    schema = client.get("/openapi.json").json()

    assert "/tailor-docx" in schema["paths"]
    assert "post" in schema["paths"]["/tailor-docx"]
