import asyncio
import io
import logging
import os
import re
import time
import uuid
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from pypdf import PdfReader
from starlette.concurrency import run_in_threadpool

from app.errors import AppError
from app.middleware import BodyLimitMiddleware, RateLimitMiddleware
from app.schemas import (
    MAX_JD_CHARS,
    MAX_RESUME_CHARS,
    MIN_TEXT_CHARS,
    MatchRequest,
    MatchResponse,
)
from app.services.ats_audit import audit_resume
from app.services.extractor import extract_skills
from app.services.matcher import match_resume_to_jd
from app.services.model_manager import ModelUnavailableError, model_manager
from app.services.parser import (
    extract_text_from_docx_bytes,
    extract_text_from_pdf_bytes,
)
from app.services.tailor import bridge_aliases, build_resume_docx

logger = logging.getLogger("resume_job_matcher")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

STATIC_DIR = Path(__file__).parent / "static"

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

SUPPORTED_SUFFIXES = {".pdf", ".docx"}

READ_ERROR = (
    "Could not read any text from this file. It may be corrupted, "
    "password-protected, or a scanned image. Try re-exporting it as a "
    "text-based PDF or DOCX from Word or Google Docs."
)

MAX_UPLOAD_BYTES = 5_000_000
UPLOAD_CHUNK_SIZE = 64 * 1024
MAX_DOCX_MEMBERS = 2000
MAX_DOCX_UNCOMPRESSED = 50_000_000
MAX_PDF_PAGES = 40

HEAVY_OP_LIMIT = 4
HEAVY_QUEUE_WAIT_SECONDS = 30.0

SERVER_BUSY_MESSAGE = (
    "The service is handling a lot of requests right now. "
    "Please wait a moment and try again."
)

REQUEST_ID_RE = re.compile(r"[^A-Za-z0-9_-]+")
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")

_semaphore = None
_semaphore_loop = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("PRELOAD_MODEL", "0").strip().lower() in {"1", "true", "yes"}:
        try:
            await run_in_threadpool(model_manager.get_model)
            logger.info("Embedding model preloaded")
        except ModelUnavailableError:
            logger.error(
                "PRELOAD_MODEL is set but the embedding model failed to load; "
                "the service will report not-ready until it can load"
            )
    yield


app = FastAPI(title="Resume Job Matcher", lifespan=lifespan)

app.add_middleware(BodyLimitMiddleware)
app.add_middleware(RateLimitMiddleware)


def _new_request_id(incoming):
    if incoming:
        cleaned = REQUEST_ID_RE.sub("", incoming)[:64]
        if cleaned:
            return cleaned
    return uuid.uuid4().hex[:12]


def _get_semaphore():
    global _semaphore, _semaphore_loop

    loop = asyncio.get_running_loop()
    if _semaphore is None or _semaphore_loop is not loop:
        _semaphore = asyncio.Semaphore(HEAVY_OP_LIMIT)
        _semaphore_loop = loop
    return _semaphore


async def _run_heavy(func, *args):
    semaphore = _get_semaphore()

    try:
        await asyncio.wait_for(semaphore.acquire(), timeout=HEAVY_QUEUE_WAIT_SECONDS)
    except TimeoutError:
        raise AppError(503, "server_busy", SERVER_BUSY_MESSAGE) from None

    try:
        return await run_in_threadpool(func, *args)
    except ModelUnavailableError as exc:
        raise AppError(503, "model_unavailable", str(exc)) from exc
    finally:
        semaphore.release()


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = _new_request_id(request.headers.get("X-Request-ID"))
    request.state.request_id = request_id
    started = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Unhandled error [%s] %s %s",
            request_id,
            request.method,
            request.url.path,
        )
        response = JSONResponse(
            status_code=500,
            content={
                "detail": {
                    "code": "internal_error",
                    "message": "Something went wrong on our side. " "Please try again.",
                },
                "request_id": request_id,
            },
        )

    response.headers["X-Request-ID"] = request_id
    duration_ms = round((time.perf_counter() - started) * 1000, 1)
    logger.info(
        "%s %s -> %s (%sms) [%s]",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request_id,
    )
    return response


def _error_body(request, code, message, extra=None):
    body = {"detail": {"code": code, "message": message}}
    if extra:
        body.update(extra)
    request_id = getattr(getattr(request, "state", None), "request_id", None)
    if request_id:
        body["request_id"] = request_id
    return body


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(request, exc.code, exc.message, exc.extra),
        headers=exc.headers or None,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()

    locations = {
        str(part)
        for error in errors
        for part in error.get("loc", ())
        if part not in {"body", "query"}
    }
    too_long = any(
        error.get("type") in {"string_too_long", "too_long"} for error in errors
    )

    field_specs = [
        ("resume_text", "resume", MAX_RESUME_CHARS),
        ("job_description", "job description", MAX_JD_CHARS),
    ]
    affected = [
        (label, max_chars)
        for field, label, max_chars in field_specs
        if field in locations
    ]

    if too_long and affected:
        parts = [
            f"Your {label} is too long. Keep it under {max_chars:,} characters."
            for label, max_chars in affected
        ]
    elif affected:
        parts = [
            f"Your {label} needs at least {MIN_TEXT_CHARS} characters of "
            "actual text."
            for label, _ in affected
        ]
    else:
        parts = [
            f"Both your resume and the job description need at least "
            f"{MIN_TEXT_CHARS} characters of actual text."
        ]

    summaries = []
    for error in errors:
        location = ".".join(
            str(part) for part in error.get("loc", ()) if part not in {"body", "query"}
        )
        message = error.get("msg", "Invalid value")
        summaries.append(f"{location}: {message}" if location else message)

    message = " ".join(parts)
    if summaries:
        message = f"{message} ({'; '.join(summaries[:3])})"

    return JSONResponse(
        status_code=422,
        content=_error_body(request, "invalid_input", message),
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    logger.exception(
        "Unhandled error [%s]",
        getattr(getattr(request, "state", None), "request_id", "unknown"),
    )
    return JSONResponse(
        status_code=500,
        content=_error_body(
            request,
            "internal_error",
            "Something went wrong on our side. Please try again.",
        ),
    )


def _require_supported(filename):
    suffix = Path(filename or "").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise AppError(
            400, "unsupported_file", "Only PDF and DOCX resumes are supported."
        )


def _validate_text_field(value, label, max_chars=MAX_JD_CHARS):
    stripped = (value or "").strip()
    if len(stripped) < MIN_TEXT_CHARS:
        raise AppError(
            422,
            "invalid_input",
            f"The {label} needs at least {MIN_TEXT_CHARS} characters of "
            "actual text.",
        )
    if len(stripped) > max_chars:
        raise AppError(
            422,
            "invalid_input",
            f"The {label} is too long. Keep it under {max_chars:,} characters.",
        )
    return stripped


def _sniff_kind(data):
    if b"%PDF-" in data[:1024]:
        return "pdf"
    if data[:2] == b"PK":
        return "docx"
    return None


def _check_docx_archive(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            names = set(archive.namelist())
    except zipfile.BadZipFile:
        raise AppError(
            400,
            "unsupported_file",
            "This DOCX file is corrupted or not a real DOCX. "
            "Re-export it and try again.",
        ) from None

    if any(info.flag_bits & 0x1 for info in infos):
        raise AppError(
            400, "unsupported_file", "Password-protected files are not supported."
        )

    uncompressed = sum(info.file_size for info in infos)
    if len(infos) > MAX_DOCX_MEMBERS or uncompressed > MAX_DOCX_UNCOMPRESSED:
        raise AppError(
            413,
            "file_too_large",
            "This document expands to too much data to process safely. "
            "Re-save a simpler version and try again.",
        )

    if "word/document.xml" not in names:
        raise AppError(
            400,
            "unsupported_file",
            "This file is a ZIP archive but not a Word DOCX document.",
        )


def _validate_upload(data, filename):
    suffix = Path(filename or "").suffix.lower()
    kind = _sniff_kind(data)

    if kind is None:
        raise AppError(
            400,
            "unsupported_file",
            "This file doesn't look like a real PDF or DOCX. "
            "Re-export it and try again.",
        )

    expected = suffix.lstrip(".")
    if kind != expected:
        raise AppError(
            400,
            "unsupported_file",
            f"The file content doesn't match its {expected.upper()} extension. "
            "Re-export it and try again.",
        )

    if kind == "docx":
        _check_docx_archive(data)

    if kind == "pdf":
        try:
            page_count = len(PdfReader(io.BytesIO(data)).pages)
        except Exception:
            page_count = None
        if page_count is not None and page_count > MAX_PDF_PAGES:
            raise AppError(
                413,
                "file_too_large",
                f"This PDF has {page_count} pages. The limit is "
                f"{MAX_PDF_PAGES} pages - trim or split the document and try "
                "again.",
            )


async def _read_upload_limited(upload):
    declared_size = getattr(upload, "size", None)
    if declared_size and declared_size > MAX_UPLOAD_BYTES:
        raise AppError(
            413,
            "file_too_large",
            "This file is larger than the 5 MB limit. "
            "Export a simpler PDF or DOCX and try again.",
        )

    buffer = bytearray()
    while True:
        chunk = await upload.read(UPLOAD_CHUNK_SIZE)
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > MAX_UPLOAD_BYTES:
            raise AppError(
                413,
                "file_too_large",
                "This file is larger than the 5 MB limit. "
                "Export a simpler PDF or DOCX and try again.",
            )
    return bytes(buffer)


def _extract_file_text(data, filename):
    suffix = Path(filename or "").suffix.lower()
    if suffix == ".docx":
        return extract_text_from_docx_bytes(data)
    return extract_text_from_pdf_bytes(data)


def _safe_audit(data, filename):
    try:
        return audit_resume(data, filename)
    except Exception:
        logger.exception("ATS audit failed for %s", filename)
        return {
            "parseability_score": 0,
            "issues": [
                {
                    "severity": "high",
                    "message": "The file layout could not be analyzed.",
                    "suggestion": "Re-export a fresh text-based file from Word or "
                    "Google Docs.",
                }
            ],
            "checks_passed": [],
        }


def _process_upload_match(data, filename, jd_text):
    resume_text = _extract_file_text(data, filename)
    audit = _safe_audit(data, filename)

    if not resume_text.strip():
        raise AppError(
            422,
            "unreadable_document",
            READ_ERROR,
            extra={"ats_audit": audit},
        )

    result = match_resume_to_jd(resume_text, jd_text)
    result["ats_audit"] = audit
    return result


def _tailor_from_resume_text(resume_text, jd_text):
    jd_skills = extract_skills(jd_text)
    bridged = bridge_aliases(resume_text, jd_skills)
    return build_resume_docx(bridged["text"])


def _sanitize_filename(name):
    cleaned = SAFE_FILENAME_RE.sub("_", str(name or "")).strip("._-")
    return cleaned[:60] or "resume"


@app.get("/", include_in_schema=False)
def read_root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/healthz")
def healthz():
    return {"status": "ok", "model_loaded": model_manager.is_loaded}


@app.get("/readyz")
def readyz():
    try:
        model_manager.get_model()
    except ModelUnavailableError as exc:
        raise AppError(503, "model_unavailable", str(exc)) from exc
    return {"status": "ready", "model_loaded": True}


@app.post("/match", response_model=MatchResponse)
async def match_endpoint(payload: MatchRequest):
    return await _run_heavy(
        match_resume_to_jd, payload.resume_text, payload.job_description
    )


@app.post("/match-upload", response_model=MatchResponse)
async def match_upload_endpoint(
    resume_file: UploadFile = File(...),
    job_description: str = Form(...),
):
    filename = resume_file.filename or "resume.pdf"
    _require_supported(filename)
    jd_text = _validate_text_field(job_description, "job description")

    data = await _read_upload_limited(resume_file)
    _validate_upload(data, filename)

    return await _run_heavy(_process_upload_match, data, filename, jd_text)


@app.post("/tailor-docx")
async def tailor_docx_endpoint(
    job_description: str = Form(...),
    resume_text: str | None = Form(None),
    resume_file: UploadFile | None = File(None),
):
    jd_text = _validate_text_field(job_description, "job description")

    if resume_file is not None:
        filename = resume_file.filename or "resume.pdf"
        _require_supported(filename)
        data = await _read_upload_limited(resume_file)
        _validate_upload(data, filename)
        resume_source = _extract_file_text(data, filename)
        if not resume_source.strip():
            raise AppError(422, "unreadable_document", READ_ERROR)
        base_name = Path(filename).stem
    elif resume_text and resume_text.strip():
        resume_source = _validate_text_field(
            resume_text, "resume", max_chars=MAX_RESUME_CHARS
        )
        base_name = "resume"
    else:
        raise AppError(
            422,
            "invalid_input",
            "Provide resume text or a PDF/DOCX resume file.",
        )

    docx_bytes = await _run_heavy(_tailor_from_resume_text, resume_source, jd_text)

    filename = f"{_sanitize_filename(base_name)}_tailored.docx"
    return Response(
        content=docx_bytes,
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
