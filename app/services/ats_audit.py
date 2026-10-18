import io
import re

import pdfplumber
from docx import Document

from app.services.contacts import EMAIL_RE, LINK_RE, looks_like_phone
from app.services.docx_evidence import build_docx_evidence
from app.services.headings import REQUIRED_HEADINGS, match_headings
from app.services.layout import has_columnar_layout

INVISIBLE_CHARS_RE = re.compile(r"[\u00ad\u200b\u200c\u200d\ufeff]")
EMOJI_RE = re.compile("[\U0001f000-\U0001faff\u2600-\u27bf\u2b00-\u2bff\ufe0f\u20e3]")

NON_STANDARD_DATES_RE = re.compile(
    r"\b(?:summer|spring|fall|autumn|winter)\s+\d{4}\b" r"|(?<!\d)(?<![\w])'\d{2}\b",
    re.IGNORECASE,
)

DECORATIVE_IMAGE_MAX_AREA_RATIO = 0.005

CONTACT_ZONE_PT = 24.0

SEVERITY_PENALTY = {"high": 25, "medium": 12, "low": 5}


def _filename_issues(filename):
    issues = []
    lowered = filename.lower()

    if not re.search(r"(resume|cv)", lowered):
        issues.append(
            (
                "low",
                f"The filename '{filename}' doesn't mention that it is a resume.",
                "Rename it to something like 'Firstname_Lastname_Resume.pdf'.",
            )
        )
    if re.search(r"(final|copy|v\d|version|updated|new|draft)", lowered):
        issues.append(
            (
                "low",
                f"The filename '{filename}' contains filler words like 'final' or "
                "'copy'.",
                "Use a clean name: 'Firstname_Lastname_Resume.pdf'.",
            )
        )
    return issues


def _missing_headings(text):
    found = set()
    for line in text.splitlines():
        for title in match_headings(line):
            found.add(title)
    return [title for title in REQUIRED_HEADINGS if title not in found]


def _has_contact(text):
    if EMAIL_RE.search(text) or looks_like_phone(text):
        return True
    return bool(LINK_RE.search(text)) and len(text.split()) <= 12


def _text_hygiene_issues(text, issues, passed):
    if INVISIBLE_CHARS_RE.search(text):
        issues.append(
            (
                "low",
                "Hidden characters (zero-width spaces or soft hyphens) were "
                "found in the text.",
                "Remove them so parsers and recruiters see exactly what you " "wrote.",
            )
        )
    else:
        passed.append("No hidden characters")

    if EMOJI_RE.search(text):
        issues.append(
            (
                "low",
                "Emoji or decorative symbols were found in the text.",
                "Replace them with plain text; some parsers drop or scramble "
                "symbols.",
            )
        )
    else:
        passed.append("No emoji or decorative symbols")


def _build_audit(pages, filename):
    issues = []
    passed = []

    text_parts = []
    word_count = 0
    columnar_pages = 0
    table_pages = 0
    image_pages = 0
    zone_contact = False
    body_contact = False

    for page in pages:
        width = page.width or 612
        height = page.height or 792

        try:
            words = page.extract_words()
        except Exception:
            words = []

        word_count += len(words)
        try:
            text_parts.append(page.extract_text() or "")
        except Exception:
            text_parts.append("")

        if has_columnar_layout(words, width):
            columnar_pages += 1

        try:
            if page.find_tables():
                table_pages += 1
        except Exception:
            pass

        zone_text = " ".join(
            w["text"]
            for w in words
            if w["top"] < CONTACT_ZONE_PT or w["bottom"] > height - CONTACT_ZONE_PT
        )
        body_text = " ".join(
            w["text"]
            for w in words
            if w["top"] >= CONTACT_ZONE_PT and w["bottom"] <= height - CONTACT_ZONE_PT
        )

        if EMAIL_RE.search(zone_text) or looks_like_phone(zone_text):
            zone_contact = True
        elif LINK_RE.search(zone_text) and len(zone_text.split()) <= 12:
            zone_contact = True

        if _has_contact(body_text):
            body_contact = True

        try:
            images = page.images or []
        except Exception:
            images = []

        if images:
            page_area = width * height
            largest_area = 0.0
            for image in images:
                image_width = float(image.get("x1", 0)) - float(image.get("x0", 0))
                image_height = float(image.get("bottom", 0)) - float(
                    image.get("top", 0)
                )
                largest_area = max(largest_area, image_width * image_height)
            large_enough = (
                page_area > 0
                and largest_area / page_area > DECORATIVE_IMAGE_MAX_AREA_RATIO
            )
            if large_enough or len(words) < 50:
                image_pages += 1

    contact_in_zone = zone_contact and not body_contact

    text = "\n".join(text_parts)
    page_count = len(pages)

    _text_hygiene_issues(text, issues, passed)

    if word_count == 0:
        issues.append(
            (
                "high",
                "No selectable text was found in this PDF "
                "(it looks like a scan or an image).",
                "ATS software cannot read scanned resumes. Export a text-based "
                "PDF straight from Word or Google Docs.",
            )
        )
    elif word_count < 50:
        issues.append(
            (
                "medium",
                "Very little text could be extracted from this PDF.",
                "Re-export a text-based PDF from Word or Google Docs instead of "
                "an image-heavy design tool.",
            )
        )
    else:
        passed.append("Text extracts cleanly")

    if page_count > 2:
        issues.append(
            (
                "medium",
                f"The resume is {page_count} pages long.",
                "Most recruiters and parsers prefer 1-2 pages. Trim older or "
                "less relevant content.",
            )
        )
    else:
        passed.append("Length is 1-2 pages")

    if columnar_pages:
        issues.append(
            (
                "medium",
                "This PDF appears to use a multi-column or heavily aligned "
                "layout, which some parsers read in the wrong order.",
                "Check by copying all text from the PDF into a plain editor. If "
                "the order looks scrambled, switch to a single-column layout.",
            )
        )
    else:
        passed.append("Single-column layout")

    if table_pages:
        issues.append(
            (
                "medium",
                "Tables were detected in the PDF. Many ATS parsers scramble "
                "the content inside tables.",
                "Replace tables with simple lines of text.",
            )
        )
    else:
        passed.append("No tables detected")

    if image_pages:
        issues.append(
            (
                "medium",
                f"{image_pages} page(s) contain images or graphics. Parsers "
                "ignore images, so any text inside them is invisible to ATS.",
                "Make sure every important detail is also typed as plain text.",
            )
        )
    else:
        passed.append("No images detected")

    if contact_in_zone:
        issues.append(
            (
                "high",
                "Your contact details appear in the header or footer area of "
                "the page. Many parsers ignore headers and footers.",
                "Move your email, phone, and LinkedIn into the main body, right "
                "under your name.",
            )
        )
    else:
        passed.append("No contact details stuck in header/footer")

    missing_headings = _missing_headings(text)
    if missing_headings:
        issues.append(
            (
                "low",
                "Standard section headings not found: "
                + ", ".join(missing_headings)
                + ".",
                "Use standard titles like 'Experience', 'Education', and "
                "'Skills' so parsers can classify each section.",
            )
        )
    else:
        passed.append("Standard section headings found")

    if NON_STANDARD_DATES_RE.search(text):
        issues.append(
            (
                "low",
                "Non-standard date formats found (e.g. 'Summer 2021' or ''21').",
                "Write dates as 'Month YYYY' (e.g. 'May 2021 - Present') so "
                "parsers can read your timeline.",
            )
        )
    else:
        passed.append("Date formats look parseable")

    filename_issues = _filename_issues(filename)
    if filename_issues:
        for severity, message, suggestion in filename_issues:
            issues.append((severity, message, suggestion))
    else:
        passed.append("Filename is clean")

    return issues, passed, word_count


def _finalize_audit(issues, passed, has_text=True):
    penalty = sum(SEVERITY_PENALTY[severity] for severity, _, _ in issues)
    score = max(0, 100 - penalty)

    if not has_text:
        score = min(score, 20)

    return {
        "parseability_score": score,
        "issues": [
            {"severity": severity, "message": message, "suggestion": suggestion}
            for severity, message, suggestion in issues
        ],
        "checks_passed": passed,
    }


def audit_pdf(file_bytes, filename="resume.pdf"):
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        pages = list(pdf.pages)
        issues, passed, word_count = _build_audit(pages, filename)

    return _finalize_audit(issues, passed, has_text=word_count > 0)


def _text_quality_checks(text, issues, passed):
    word_count = len(text.split())

    if word_count == 0:
        issues.append(
            (
                "high",
                "No text was found in this document.",
                "ATS software cannot read empty or image-only files. Export a "
                "text-based file with your content typed out.",
            )
        )
    elif word_count < 50:
        issues.append(
            (
                "medium",
                "Very little text could be extracted from this document.",
                "Make sure the full resume content is typed text, not images.",
            )
        )
    else:
        passed.append("Text extracts cleanly")

    missing_headings = _missing_headings(text)
    if missing_headings:
        issues.append(
            (
                "low",
                "Standard section headings not found: "
                + ", ".join(missing_headings)
                + ".",
                "Use standard titles like 'Experience', 'Education', and "
                "'Skills' so parsers can classify each section.",
            )
        )
    else:
        passed.append("Standard section headings found")

    if NON_STANDARD_DATES_RE.search(text):
        issues.append(
            (
                "low",
                "Non-standard date formats found (e.g. 'Summer 2021' or ''21').",
                "Write dates as 'Month YYYY' (e.g. 'May 2021 - Present') so "
                "parsers can read your timeline.",
            )
        )
    else:
        passed.append("Date formats look parseable")

    return word_count


def audit_docx(file_bytes, filename="resume.docx"):
    try:
        document = Document(io.BytesIO(file_bytes))
    except Exception:
        return _finalize_audit(
            [
                (
                    "high",
                    "This DOCX file could not be read.",
                    "Try re-saving it from Word or Google Docs.",
                )
            ],
            [],
            has_text=False,
        )

    evidence = build_docx_evidence(document)
    text = "\n".join(evidence["zone_lines"] + evidence["body_lines"])

    issues = []
    passed = []

    table_count = evidence["data_table_count"]
    if table_count:
        issues.append(
            (
                "medium",
                f"{table_count} table(s) were detected. Many ATS parsers "
                "scramble the content inside tables.",
                "Replace tables with simple lines of text.",
            )
        )
    else:
        passed.append("No tables detected")

    image_count = evidence["image_count"]
    if image_count:
        large_image = (
            evidence["largest_image_area_ratio"] > DECORATIVE_IMAGE_MAX_AREA_RATIO
        )
        if large_image or len(text.split()) < 50:
            issues.append(
                (
                    "low",
                    f"{image_count} image(s) were detected.",
                    "Parsers ignore images. Make sure every important detail is "
                    "also typed as plain text.",
                )
            )
        else:
            passed.append("Images are small and decorative")
    else:
        passed.append("No images")

    if evidence["multi_column"]:
        issues.append(
            (
                "medium",
                "This document uses a multi-column layout, which some parsers "
                "read in the wrong order.",
                "Switch to a single-column layout so the text reads top to " "bottom.",
            )
        )
    else:
        passed.append("Single-column layout")

    if evidence["has_text_boxes"]:
        issues.append(
            (
                "medium",
                "Text boxes or floating shapes were detected. Many ATS "
                "parsers skip content inside them.",
                "Move the text out of text boxes into normal paragraphs.",
            )
        )
    else:
        passed.append("No text boxes or floating shapes")

    zone_text = "\n".join(evidence["zone_lines"])
    body_text = "\n".join(evidence["body_lines"])

    if _has_contact(zone_text):
        zone_contact = True
    else:
        zone_contact = False
    body_contact = _has_contact(body_text)

    if zone_contact and not body_contact:
        issues.append(
            (
                "high",
                "Your contact details appear in the header or footer area. "
                "Many parsers ignore headers and footers.",
                "Move your email, phone, and LinkedIn into the main body, "
                "right under your name.",
            )
        )
    else:
        passed.append("No contact details stuck in header/footer")

    word_count = _text_quality_checks(text, issues, passed)
    _text_hygiene_issues(text, issues, passed)

    filename_issues = _filename_issues(filename)
    if filename_issues:
        for severity, message, suggestion in filename_issues:
            issues.append((severity, message, suggestion))
    else:
        passed.append("Filename is clean")

    return _finalize_audit(issues, passed, has_text=word_count > 0)


def audit_resume(file_bytes, filename="resume.pdf"):
    lower = (filename or "").lower()
    if lower.endswith(".docx"):
        return audit_docx(file_bytes, filename)
    return audit_pdf(file_bytes, filename)
