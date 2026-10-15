# Resume Job Matcher

> Built and maintained by **Goutham sai Goparaju** — gouthamsaigoparaju@gmail.com
> GitHub: https://github.com/Goutham011

A FastAPI-based backend service that evaluates how well a resume matches a job description using:

* keyword skill matching
* semantic similarity using transformer embeddings
* skill gap analysis

The API extracts skills from resumes and job descriptions, computes a match score, and highlights missing requirements.

This project demonstrates backend API development, NLP integration, testing, CI pipelines, and clean Python project structure.

---

# Features

* Resume ↔ Job Description matching
* Semantic similarity scoring using Sentence Transformers
* Skill extraction from text
* Skill gap detection
* PDF resume upload support
* FastAPI REST API
* Automated testing with Pytest
* Code formatting with Black
* Linting with Ruff
* GitHub Actions CI pipeline

---

# Tech Stack

* Python 3.12
* FastAPI
* Sentence Transformers
* PyPDF
* Pytest
* Black
* Ruff
* GitHub Actions

---

# Project Structure

```
resume-job-matcher
│
├── app
│   ├── main.py
│   ├── schemas.py
│   │
│   ├── services
│   │   ├── matcher.py
│   │   ├── extractor.py
│   │   └── parser.py
│   │
│   └── utils
│       └── text_cleaner.py
│
├── tests
│
├── .github/workflows
│   └── ci.yml
│
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

# Installation

Clone the repository

```bash
git clone https://github.com/Goutham011/resume-job-matcher.git
cd resume-job-matcher
```

Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

# Running the API

Start the server

```bash
uvicorn app.main:app --reload
```

Open the interactive API documentation

```
http://127.0.0.1:8000/docs
```

---

# API Usage

## Match resume text

POST `/match`

Example request

```json
{
  "resume_text": "Python developer with FastAPI, SQL, and Docker experience",
  "job_description": "Looking for a backend engineer with Python, FastAPI, SQL, Docker, AWS and Kubernetes"
}
```

Example response

```json
{
  "overall_score": 78.7,
  "matched_skills": ["aws", "docker", "fastapi", "python", "sql"],
  "missing_skills": ["kubernetes"],
  "resume_keywords": ["aws", "docker", "fastapi", "python", "rest api", "sql"],
  "jd_keywords": ["aws", "docker", "fastapi", "kubernetes", "python", "sql"],
  "explanation": "This is a strong match. Matched skills: aws, docker, fastapi, python, sql. Missing skills: kubernetes."
}
```

---

## Upload resume file

POST `/match-upload`

Supports:

* PDF resumes

Example form data

```
resume_file: resume.pdf
job_description: Backend engineer with Python and FastAPI
```

---

# Running Tests

```bash
pytest
```

---

# Code Quality

Formatting

```bash
black .
```

Linting

```bash
ruff check .
```

---

# Continuous Integration

GitHub Actions automatically runs on every push and pull request.

The pipeline performs:

* dependency installation
* code formatting checks
* lint checks
* test execution

---

# Future Improvements

Possible enhancements:

* DOCX resume support
* resume section analysis
* better skill extraction using NLP
* web frontend
* containerization with Docker
* deployment to cloud platforms

---

# Author

**Goutham sai Goparaju**
* Email: gouthamsaigoparaju@gmail.com
* GitHub: https://github.com/Goutham011