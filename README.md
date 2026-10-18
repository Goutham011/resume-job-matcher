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
- Copy detection: word-for-word and rephrased content mirrored from the
  posting (including copies split across lines and re-assembled clauses),
  with score penalties
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
    "content_mirrored": false,
    "content_paraphrased": false,
    "content_stuffing": false,
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
  the verb, `SEM`/`ML`/`DL` capitalized usages, `TS/SCI` never counted as
  TypeScript). Soft skills are reported with `kind: "soft"` and carry half
  weight, so a comfort match never outweighs a core one.
- **Content integrity adjustments:** copied wording is detected in tiers —
  verbatim sentences (≥ 0.95 cosine on sentence units, including copies split
  across neighbouring lines), lightly rephrased versions (≥ 0.88), and
  re-assembled clauses (shared 4–6 word sequences) — and penalises content
  similarity (×0.8 / ×0.9). Dense skill lists with no supporting prose trigger
  keyword-stuffing handling (×0.85 on content, and coverage blended as 25%
  raw / 75% prose-evidenced).

The overall score is a weighted blend, clamped to 0–100.

## ATS Audit

The audit grades parseability (0–100) with high/medium/low issue severities:

- No selectable text (scanned/image PDF) or very little text — DOCX header,
  footer, header-table, and text-box content all count toward extraction
- Multi-column layouts detected from word geometry
- Data tables in PDFs/DOCX (single-cell layout tables are ignored)
- Contact details confined to the header/footer zone (top/bottom 24 pt),
  including contact info placed inside header tables
- Missing standard headings (Experience, Education, Skills — matching combined
  variants like `Work History/Academic Background/Core Competencies`
  and `Skills & Tools`)
- Non-standard date formats (`Summer 2021`, `'21`) with word-boundary guards
  so apostrophes inside words never trigger
- Large images on thin-text pages (small decorative logos pass)
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
| 413  | `file_too_large`    | Upload exceeds 5 MB, PDF exceeds 40 pages, or DOCX expands beyond safety caps |
| 413  | `payload_too_large` | JSON body over 1.5 MB or multipart body over 6 MB |
| 422  | `invalid_input`     | Missing/too-short text fields (message names the field) |
| 422  | `unreadable_document` | No text could be extracted (includes `ats_audit`) |
| 429  | `rate_limited`      | More than 60 requests per minute from one client |
| 503  | `model_unavailable` | Embedding model could not be loaded            |
| 503  | `server_busy`       | Heavy-work queue saturated; retry later        |
| 500  | `internal_error`    | Unexpected failure (details logged, not leaked) |

## Limits and Guarantees

- Uploads: 5 MB max; read in 64 KB chunks with an early abort past the cap
- PDFs over 40 pages are rejected with an explicit message before any text
  extraction runs
- Request bodies: JSON capped at 1.5 MB, multipart at 6 MB, enforced before
  parsing; oversized bodies are drained with a timeout so connections reset
  cleanly
- Rate limiting: 60 requests per minute per client, returning `429` with a
  request ID
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
| `SKILL_CONFIG_PATH`       | `app/data/skills.json`           | Override the cross-domain skill config file |
| `TRUST_PROXY`             | unset                            | `1` uses `X-Forwarded-For` for client rate-limit keys |
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
- Copy detection covers verbatim, lightly rephrased, and re-assembled text;
  heavy synonym-level rewriting with no shared word sequences may pass

## Future Improvements

- OCR fallback for scanned resumes
- Per-industry alias packs
- Persistent score history and comparison
- Dockerfile and cloud deployment guide

---

## Refinements and Change Log

A focused accuracy-and-hardening pass across every service in the pipeline.
Grouped by area:

### Skill extraction and matching

- Context-aware predicates: `Excel` the product vs. `excel` the verb (lowercase
  only counts with a technical cue or inside a skill list), `TS` counts as
  TypeScript only outside clearance contexts (`TS/SCI`, classified, government,
  DoD), and `SEM`/`ML`/`DL` require the capitalized product form.
- Cross-domain skill configuration lives in `app/data/skills.json` (60+
  configurable entries spanning finance, healthcare, legal, design, product,
  operations, cloud, data, and trades), validated at load time and overridable
  via `SKILL_CONFIG_PATH`. The merged vocabulary covers 150+ skills, 15 of them
  soft.
- Soft skills carry half weight in coverage instead of full weight.
- Keyword-stuffing detection: dense skill dumps are classified by an
  inventory-line classifier (word counts, separator shape, vocabulary ratio),
  flagged resumes take a ×0.85 content penalty, and skill coverage blends as
  25% raw / 75% prose-evidenced — so listing skills without work history cannot
  inflate the score.
- Vocabulary construction filters stop words and boilerplate, so fragments like
  "and" can never create alias matches.

### Copy detection (new)

- Two-tier mirror engine comparing sentence units (≥ 4 words) between the
  resume and the posting: verbatim (≥ 0.95 similarity) and rephrased (≥ 0.88).
- Resume units are compared both individually and as merged adjacent pairs, so
  copies that split a compound paragraph across shorter lines are still caught.
- Phrase-echo tier: shared word-for-word 4–6 word sequences flag re-assembled
  copies that embeddings alone miss; verdicts require ≥ 3 affected units and
  ≥ 50% resume coverage.
- Effects: mirrored content ×0.8, rephrased ×0.9, with dedicated writing issues
  and recommendations; `content_mirrored`, `content_paraphrased`, and
  `content_stuffing` are exposed in the score breakdown.

### Reviewer and advice

- Structure review shares the heading matcher with the auditor, so combined
  headings (`Work History`, `Academic Background`, `Core Competencies`) no
  longer read as missing sections.
- Advice rewritten to stop suggesting the posting's wording be mirrored; it now
  suggests using the posting's vocabulary around your own work.

### Contacts

- Phone detection rebuilt: minimum 10 digits (9 only with a country code or
  parentheses), near-text vetoes for salary/budget/badge/ID/reference/account/zip
  contexts, digit-group shape checks, and a phone-cue requirement for bare
  digit runs.
- Shared canonical email and profile-link patterns across the auditor, reviewer,
  parser, and tailoring export.

### ATS audit

- New shared DOCX evidence model (`docx_evidence.py`): header/footer
  paragraphs, header/footer tables, and text boxes are all included in
  extraction and auditing.
- Header-table contact details are detected instead of being treated as
  missing.
- Single-cell tables are treated as layout, not data tables.
- Image policy: small decorative images pass; large images on thin-text pages
  are flagged.
- Text-box-only resumes keep their word count and are no longer floored like
  scanned files.
- Short-year date detection (`'21`) uses word-boundary guards.

### Requirements

- Year patterns parse "N+ years", "N-M years" (lower bound), "at least/minimum
  N years", and generic "N years" forms in priority order.
- Experience scoping: claims in a Summary no longer satisfy the years
  requirement, experience text is limited to front matter plus the experience
  sections, and duty text ("4 years of coursework") no longer inflates the
  estimate.

### Tailoring export

- Front-matter classification rewritten: name, headline, contact line, and
  summary are recognized individually and rendered accordingly (bold name,
  normal-weight headline, intact contact line, summary under its own heading).

### API and middleware

- Request caps: JSON 1.5 MB, multipart 6 MB, PDFs 40 pages, uploads 5 MB.
- Rate limiting: 60 requests per minute per client returning `429`, with
  per-key pruning so unbounded keys cannot grow memory.
- `TRUST_PROXY=1` opts into `X-Forwarded-For` client keys.
- 422 validation messages now name the offending field.

### Web UI

- Instant client-side 5 MB checks in both upload flows.
- Coverage section explains why using the posting's vocabulary matters.

### Tests

- Suite expanded to 166 tests: mirror tiers, stuffing bounds (score gain ≤ 15
  points over baseline), contacts, heading variants, ATS edge cases (header
  tables, images, text boxes, short years), requirements parsing, API limits
  (page caps, payload caps, rate limiting), tailoring output, and soft-skill
  weighting. Deterministic fake model by default; real-model tests behind
  `RUN_MODEL_TESTS=1`; DOCX/PDF builder helpers for realistic fixtures.

---

## Author

**Goutham sai Goparaju**
- Email: gouthamsaigoparaju@gmail.com
- GitHub: https://github.com/Goutham011
