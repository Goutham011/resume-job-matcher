from app.services.ats_audit import (
    NON_STANDARD_DATES_RE,
    audit_docx,
    audit_pdf,
    audit_resume,
)
from app.services.contacts import looks_like_phone
from app.services.headings import match_heading
from tests.docx_builder import (
    make_docx,
    make_docx_with_header_contact,
    make_docx_with_header_table_contact,
    make_docx_with_image,
    make_docx_with_table,
    make_docx_with_textbox,
)
from tests.pdf_builder import CLEAN_LINES, make_pdf

CLEAN_DOCX_LINES = [
    "Goutham Sai",
    "goutham@example.com | +1 555 123 4567 | linkedin.com/in/goutham",
    "Experience",
    "Built REST API services in Python and FastAPI for three years.",
    "Led a team of three engineers migrating twelve services to Docker.",
    "Designed PostgreSQL schemas processing over ten thousand orders.",
    "Automated nightly data checks saving the team ten hours weekly.",
    "Mentored two junior developers and reviewed hundreds of pull requests.",
    "Cut cloud costs by aligning AWS instances with real demand.",
    "Skills",
    "Python, FastAPI, SQL, Docker, AWS, Git, Linux, Kubernetes",
    "Education",
    "Bachelor of Technology in Computer Science, 2022",
]


def test_clean_single_column_pdf_passes():
    audit = audit_pdf(make_pdf(CLEAN_LINES), "Goutham_Resume.pdf")

    high_issues = [i for i in audit["issues"] if i["severity"] == "high"]
    assert not high_issues
    assert audit["parseability_score"] >= 80
    assert "Text extracts cleanly" in audit["checks_passed"]
    assert "No contact details stuck in header/footer" in audit["checks_passed"]


def test_pdf_with_contact_in_header_is_flagged():
    body = [line for line in CLEAN_LINES if "@" not in line[2]]
    lines = [(50, 15, "goutham@example.com | +1 555 123 4567")] + body
    audit = audit_pdf(make_pdf(lines), "resume.pdf")

    messages = " ".join(issue["message"] for issue in audit["issues"])
    assert "header" in messages.lower()
    assert "No contact details stuck in header/footer" not in audit["checks_passed"]


def test_pdf_with_contact_just_below_zone_is_not_flagged():
    body = [line for line in CLEAN_LINES if "@" not in line[2]]
    lines = [(50, 45, "goutham@example.com | +1 555 123 4567")] + body
    audit = audit_pdf(make_pdf(lines), "resume.pdf")

    messages = " ".join(issue["message"] for issue in audit["issues"])
    assert "header" not in messages.lower()
    assert "No contact details stuck in header/footer" in audit["checks_passed"]


def test_pdf_with_header_and_body_contact_is_not_flagged():
    body = [line for line in CLEAN_LINES if "@" not in line[2]]
    contact = "goutham@example.com | +1 555 123 4567"
    lines = [(50, 15, contact), (50, 80, contact)] + body
    audit = audit_pdf(make_pdf(lines), "resume.pdf")

    assert "No contact details stuck in header/footer" in audit["checks_passed"]


def test_pdf_with_two_columns_is_flagged():
    lines = []
    for index in range(14):
        top = 100 + index * 18
        lines.append((50, top, "built scalable backend systems reliably daily"))
        lines.append((350, top, "python fastapi docker kubernetes observability"))

    audit = audit_pdf(make_pdf(lines), "resume.pdf")

    messages = " ".join(issue["message"] for issue in audit["issues"])
    assert "column" in messages.lower()


def test_date_range_not_detected_as_phone_number():
    assert looks_like_phone("+1 555 123 4567")
    assert looks_like_phone("(555) 123-4567")
    assert not looks_like_phone("2021 - 2022")
    assert not looks_like_phone("May 2021 - Present")

    body = [
        (50, 100, "Experience"),
        (50, 120, "Backend engineer building Python services for data teams."),
        (50, 140, "Shipped APIs used by internal reporting tools."),
        (50, 180, "Skills"),
        (50, 200, "Python, FastAPI, SQL, Docker, Linux"),
        (50, 240, "Education"),
        (50, 260, "Bachelor of Technology in Computer Science"),
    ]
    lines = [(50, 15, "2021 - 2022")] + body

    audit = audit_pdf(make_pdf(lines), "resume.pdf")

    messages = " ".join(issue["message"] for issue in audit["issues"])
    assert "header" not in messages.lower()
    assert "No contact details stuck in header/footer" in audit["checks_passed"]


def test_core_competencies_and_key_projects_headings_recognized():
    assert match_heading("Core Competencies") == "Skills"
    assert match_heading("KEY PROJECTS") == "Projects"

    lines = [
        "Goutham Sai",
        "goutham@example.com | +1 555 123 4567 | linkedin.com/in/goutham",
        "Core Competencies",
        "Python, FastAPI, SQL, Docker",
        "KEY PROJECTS",
        "Built a resume matcher service with FastAPI and Docker.",
        "Experience",
        "Backend engineer building Python services for data teams.",
        "Education",
        "BSc Computer Science, 2022",
    ]

    audit = audit_resume(make_docx(lines), "Goutham_Resume.docx")

    assert "Standard section headings found" in audit["checks_passed"]


def test_docx_text_boxes_are_flagged():
    data = make_docx_with_textbox("InsideTextBoxVisibleText", CLEAN_DOCX_LINES)

    audit = audit_docx(data, "Goutham_Resume.docx")

    messages = " ".join(issue["message"] for issue in audit["issues"])
    assert "text box" in messages.lower()


def test_pdf_without_text_is_flagged():
    audit = audit_pdf(make_pdf([]), "resume.pdf")

    high_issues = [i for i in audit["issues"] if i["severity"] == "high"]
    assert any("No selectable text" in issue["message"] for issue in high_issues)
    assert audit["parseability_score"] <= 50


def test_dirty_filename_is_flagged():
    audit = audit_pdf(make_pdf(CLEAN_LINES), "resume_final_v3_copy.pdf")

    messages = " ".join(issue["message"] for issue in audit["issues"])
    assert "filename" in messages.lower()


def test_audit_resume_dispatches_pdf_files():
    audit = audit_resume(make_pdf(CLEAN_LINES), "Goutham_Resume.pdf")

    assert audit["parseability_score"] >= 80


def test_clean_docx_passes():
    audit = audit_resume(make_docx(CLEAN_DOCX_LINES), "Goutham_Resume.docx")

    high_issues = [i for i in audit["issues"] if i["severity"] == "high"]
    assert not high_issues
    assert audit["parseability_score"] >= 80
    assert "Text extracts cleanly" in audit["checks_passed"]
    assert "No tables detected" in audit["checks_passed"]
    assert "No contact details stuck in header/footer" in audit["checks_passed"]


def test_docx_with_table_is_flagged():
    audit = audit_docx(
        make_docx_with_table([["Python", "5 years"], ["FastAPI", "3 years"]]),
        "resume.docx",
    )

    messages = " ".join(issue["message"] for issue in audit["issues"])
    assert "table" in messages.lower()


def test_docx_with_contact_in_header_is_flagged():
    data = make_docx_with_header_contact("goutham@example.com | +1 555 123 4567")
    audit = audit_resume(data, "resume.docx")

    messages = " ".join(issue["message"] for issue in audit["issues"])
    assert "header" in messages.lower()
    assert "No contact details stuck in header/footer" not in audit["checks_passed"]


def test_docx_recognizes_skills_and_tools_heading():
    lines = [
        "Skills & Tools" if line == "Skills" else line for line in CLEAN_DOCX_LINES
    ]
    audit = audit_resume(make_docx(lines), "Goutham_Resume.docx")

    assert "Standard section headings found" in audit["checks_passed"]


def test_invalid_docx_is_flagged():
    audit = audit_docx(b"not a real docx", "resume.docx")

    high_issues = [i for i in audit["issues"] if i["severity"] == "high"]
    assert high_issues
    assert audit["parseability_score"] <= 20


def test_docx_header_table_contact_is_detected():
    data = make_docx_with_header_table_contact("goutham@example.com")
    audit = audit_resume(data, "resume.docx")

    messages = " ".join(issue["message"] for issue in audit["issues"])
    assert "header" in messages.lower()
    assert "No contact details stuck in header/footer" not in audit["checks_passed"]


def test_docx_header_table_email_is_extracted_by_parser():
    from app.services.parser import extract_text_from_docx_bytes

    data = make_docx_with_header_table_contact("goutham@example.com")
    text = extract_text_from_docx_bytes(data)

    assert "goutham@example.com" in text


def test_single_cell_table_is_not_flagged():
    audit = audit_docx(
        make_docx_with_table([["Python, FastAPI, SQL, Docker, AWS"]]),
        "resume.docx",
    )

    assert "No tables detected" in audit["checks_passed"]


def test_textbox_only_docx_text_counts_toward_word_count():
    box_text = "Data analyst with strong reporting skills and dashboards. " * 8
    data = make_docx_with_textbox(box_text, [])
    audit = audit_docx(data, "resume.docx")

    assert "Text extracts cleanly" in audit["checks_passed"]
    assert audit["parseability_score"] > 20


def test_small_decorative_image_is_not_flagged():
    body = list(CLEAN_DOCX_LINES)
    data = make_docx_with_image(0.4, 0.4, body_lines=body)
    audit = audit_docx(data, "resume.docx")

    messages = " ".join(issue["message"] for issue in audit["issues"])
    assert "image(s) were detected" not in messages
    assert "Images are small and decorative" in audit["checks_passed"]


def test_large_image_is_flagged():
    body = list(CLEAN_DOCX_LINES)
    data = make_docx_with_image(6.0, 4.0, body_lines=body)
    audit = audit_docx(data, "resume.docx")

    messages = " ".join(issue["message"] for issue in audit["issues"])
    assert "image(s) were detected" in messages


def test_short_year_detection_requires_word_boundary():
    assert NON_STANDARD_DATES_RE.search("Graduated Summer 2021")
    assert NON_STANDARD_DATES_RE.search("Class of '21")
    assert not NON_STANDARD_DATES_RE.search("the brands'21 launch")
    assert not NON_STANDARD_DATES_RE.search("He'll 21 items")
    assert not NON_STANDARD_DATES_RE.search("2021 - 2022")
