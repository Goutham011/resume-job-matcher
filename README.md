# Resume Job Matcher & ATS Auditor

> Built and maintained by **Goutham sai Goparaju** — gouthamsaigoparaju@gmail.com
> GitHub: https://github.com/Goutham011

A FastAPI service that scores how well a resume matches a job description and
audits the resume the way applicant-tracking systems (ATS) read it.

It combines keyword skill matching, chunked semantic similarity with pinned
transformer embeddings, writing/structure review, ATS parseability auditing,
and a one-click DOCX "tailoring" export — plus a small static web UI.

---

## Features

- Resume-to-job-description match scoring (semantic similarity + skill coverage)
- Skill extraction with aliases and soft-skill detection
- Missing-skill gap analysis and dynamic keyword discovery from the job posting
- Requirement extraction (must-have vs preferred) and knockout checks (work
  authorization, years of experience)
- Writing review: spelling, grammar, punctuation, structure, clichés, and
  keyword-stuffing detection
- ATS parseability audit for PDF and DOCX: text extraction, columns, tables,
  contact details stuck in headers/footers, heading conventions, date formats,
  and filename hygiene
- DOCX tailoring export that bridges skill aliases into the resume text
- Static browser UI served at `/`
- Strict upload validation (size caps, magic-byte sniffing, ZIP-bomb guards)
- Structured error contract with request IDs for every response
- Bounded concurrency for heavy operations (no request pile-ups)

---

## Tech Stack

- Python 3.12
- FastAPI + Starlette + Uvicorn
- sentence-transformers (all-MiniLM-L6-v2, pinned revision)
- pdfplumber + pypdf (PDF), python-docx (DOCX)
- pyspellchecker
- Pytest, Black, Ruff

---

## Project Structure

```
resume-job-matcher
│
├── app
│   ├── main.py                  # FastAPI app, middleware, endpoints, guards
│   ├── schemas.py               # Pydantic request/response models
│   ├── errors.py                # AppError (status + code + message)
│   │
│   ├── services
│   │   ├── matcher.py           # scoring pipeline
│   │   ├── extractor.py         # skill extraction
│   │   ├── keywords.py          # term matching, aliases, dynamic keywords
│   │   ├── chunking.py          # token-aware chunking + pooled similarity
│   │   ├── headings.py          # resume heading normalization
│   │   ├── layout.py            # column/word layout heuristics
│   │   ├── parser.py            # PDF/DOCX text extraction
│   │   ├── ats_audit.py         # ATS parseability audit
│   │   ├── requirements.py      # requirements + knockout checks
│   │   ├── reviewer.py          # writing and style review
│   │   ├── tailor.py            # DOCX tailoring export
│   │   └── model_manager.py     # lazy, thread-safe embedding model loader
│   │
│   └── static
│       └── index.html           # single-file UI
│
├── tests                        # pytest suite (fake-model by default)
├── requirements.txt             # runtime dependencies (pinned)
├── requirements-dev.txt         # runtime + dev tooling
├── pyproject.toml               # black/ruff config
└── README.md
```

---

## Installation

```bash
git clone https://github.com/Goutham011/resume-job-matcher.git
cd resume-job-matcher

python -m venv .venv
source .venv/bin/activate

pip install -r requirements-dev.txt
```

`requirements.txt` contains the pinned runtime dependencies; the `-dev` file
adds test and lint tooling.

---

## Running the API

```bash
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- Web UI: http://127.0.0.1:8000
- Interactive docs: http://127.0.0.1:8000/docs

The embedding model downloads on first use and is cached locally. Pin the
revision with `EMBEDDING_MODEL_REVISION` (default is already pinned) so scores
stay reproducible. Set `PRELOAD_MODEL=1` to load the model at startup instead
of on the first request.

---

## API Reference

| Method | Path           | What it does                                        |
| ------ | -------------- | --------------------------------------------------- |
| GET    | `/`            | Static web UI                                       |
| GET    | `/healthz`     | Liveness probe: process is up (`status: ok`)        |
| GET    | `/readyz`      | Readiness probe: embedding model can be loaded      |
| POST   | `/match`       | Match resume text against a job description (JSON)  |
| POST   | `/match-upload`| Match an uploaded PDF/DOCX resume (multipart)       |
| POST   | `/tailor-docx` | Return a tailored DOCX built from resume + posting  |

### POST /match

```json
{
  "resume_text": "Python developer with FastAPI, SQL, and Docker experience...",
  "job_description": "Looking for a backend engineer with Python, FastAPI, SQL, Docker, AWS, and Kubernetes..."
}
```

Both fields must contain at least 20 characters of actual (non-whitespace)
text after trimming; whitespace-only input is rejected with `422`.

### POST /match-upload

Multipart form fields:

- `resume_file`: `.pdf` or `.docx` file (max 5 MB)
- `job_description`: posting text

The response is the same shape as `/match`, plus `ats_audit`. Subsequent
uploads are limited to files that sniff as real PDF/DOCX, match their
extension, and (for DOCX) pass ZIP-safety checks.

### POST /tailor-docx

Multipart form — provide **either** `resume_text` **or** `resume_file`, plus
`job_description`. Responds with
`application/vnd.openxmlformats-officedocument.wordprocessingml.document`
and a `Content-Disposition` attachment filename.

### Example response (abridged)

```json
{
  "overall_score": 78.7,
  "matched_skills": ["docker", "fastapi", "python", "sql"],
  "missing_skills": ["kubernetes"],
  "explanation": "This is a strong match...",
  "score_breakdown": {
    "content_similarity": 74.2,
    "skill_coverage": 80.0,
    "content_weight": 65,
    "skill_weight": 35,
    "resume_chunks": 3,
    "jd_chunks": 2,
    "chunk_max_tokens": 256
  },
  "keyword_coverage": [
    { "skill": "python", "status": "exact", "count": 2, "alias": null, "kind": "hard" }
  ],
  "dynamic_keywords": [
    { "term": "campaign management", "jd_count": 2, "resume_count": 1, "in_resume": true }
  ],
  "requirements": { "must_have": ["..."], "preferred": ["..."] },
  "knockout_checks": [],
  "writing_issues": [],
  "recommendations": [],
  "ats_audit": {
    "parseability_score": 92,
    "issues": [],
    "checks_passed": ["Text extracts cleanly", "Single-column layout"]
  }
}
```

---

## Scoring Methodology

- **Content similarity (default 65% of the score):** the resume and job
  description are split into token-aware chunks (max ~256 tokens, sentence and
  line boundaries respected). Each side is embedded, chunk vectors are mean
  pooled and normalized, and cosine similarity is computed on the pooled
  vectors. Long documents are chunked, never truncated.
- **Skill coverage (default 35%):** JD skills are matched against resume text
  with alias awareness and case disambiguation (`Excel` the product vs. `excel`
  the verb, `SEM`/`ML`/`DL` capitalized usages). Soft skills are tracked with
  `kind: "soft"` but weighted the same.

The overall score is a weighted blend, clamped to 0–100.

## ATS Audit

The audit grades parseability (0–100) with high/medium/low issue severities:

- No selectable text (scanned/image PDF) or very little text
- Multi-column layouts detected from word geometry
- Tables in PDFs/DOCX
- Contact details confined to the header/footer zone (top/bottom 24 pt) —
  flagged only when there is no contact evidence in the body
- Missing standard headings (Experience, Education, Skills — including
  variations like `Skills & Tools`, `TECHNICAL SKILLS`, `Professional Summary`)
- Non-standard date formats (`Summer 2021`, `'21`)
- Filename hygiene (`resume_final_v3_copy.pdf`)

## Error Contract

Every error response uses a structured detail object, and every response
carries an `X-Request-ID` header (echoed in the body for errors):

```json
{
  "detail": { "code": "file_too_large", "message": "..." },
  "request_id": "3f2c9a1b77d0"
}
```

| HTTP | code                | Meaning                                        |
| ---- | ------------------- | ---------------------------------------------- |
| 400  | `unsupported_file`  | Wrong/unknown file type, extension mismatch, not a real DOCX |
| 413  | `file_too_large`    | Upload exceeds 5 MB or DOCX expands beyond safety caps |
| 422  | `invalid_input`     | Missing/too-short text fields                  |
| 422  | `unreadable_document` | No text could be extracted (includes `ats_audit`) |
| 503  | `model_unavailable` | Embedding model could not be loaded            |
| 503  | `server_busy`       | Heavy-work queue saturated; retry later        |
| 500  | `internal_error`    | Unexpected failure (details logged, not leaked) |

## Limits and Guarantees

- Uploads: 5 MB max; read in 64 KB chunks with an early abort past the cap
- DOCX safety: rejects encrypted archives, > 2000 members, > 50 MB
  uncompressed, and ZIP files that are not Word documents
- Heavy work runs in a threadpool behind a semaphore of 4 concurrent
  operations; requests waiting longer than 30 s receive `503 server_busy`
- No persistence: resume text, uploads, and results are never written to disk
  (the only disk activity is the model cache managed by Hugging Face)

## Environment Variables

| Variable                  | Default                          | Purpose                              |
| ------------------------- | -------------------------------- | ------------------------------------ |
| `EMBEDDING_MODEL`         | `sentence-transformers/all-MiniLM-L6-v2` | Model name                   |
| `EMBEDDING_MODEL_REVISION`| pinned commit SHA                | Reproducible model revision          |
| `PRELOAD_MODEL`           | `0`                              | `1` loads the model at startup       |
| `RUN_MODEL_TESTS`         | unset                            | `1` enables real-model integration tests |

---

## Running Tests

```bash
.venv/bin/pytest -q
```

By default the suite injects a deterministic fake embedding model, so tests
run offline in about two seconds. To exercise the real model end to end:

```bash
RUN_MODEL_TESTS=1 .venv/bin/pytest -q
```

## Code Quality

```bash
.venv/bin/ruff check .
.venv/bin/black --check .
```

## Continuous Integration

GitHub Actions runs on every push and pull request: dependency installation,
Black check, Ruff check, and the full test suite.

---

## Security Notes

- Upload validation never trusts the filename or Content-Type: bytes are
  sniffed for `%PDF-` / ZIP signatures, and DOCX archives are inspected before
  parsing
- Request IDs from clients are sanitized (`[A-Za-z0-9_-]`, 64 chars max)
- Error messages are user-friendly; stack traces stay in server logs
- Download filenames are sanitized before being placed in headers

## Limitations

- Matching quality is bounded by the pinned MiniLM model; very domain-specific
  jargon may need aliases
- Scanned/image resumes are correctly rejected, not OCR'd
- DOCX visual styling is converted to a clean single-column layout when
  tailoring; complex original formatting is not preserved
- The in-process semaphore bounds memory/CPU but cannot abort a thread already
  running; worst-case latency is a slow request, not a crash

## Future Improvements

- OCR fallback for scanned resumes
- Per-industry alias packs
- Persistent score history and comparison
- Dockerfile and cloud deployment guide

---

## Author

**Goutham sai Goparaju**
- Email: gouthamsaigoparaju@gmail.com
- GitHub: https://github.com/Goutham011
