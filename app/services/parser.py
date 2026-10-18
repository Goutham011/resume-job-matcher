import re
from functools import lru_cache
from io import BytesIO

import pdfplumber
from docx import Document
from pypdf import PdfReader
from spellchecker import SpellChecker

from app.services.docx_evidence import build_docx_evidence
from app.services.extractor import SKILL_KEYWORDS
from app.services.keywords import DISPLAY_NAMES, SKILL_ALIASES
from app.services.layout import columnar_text, has_columnar_layout

PERIOD_GLUE_RE = re.compile(r"(?<=[a-zà-öø-ÿ])([.!?])(?=[A-ZÀ-Þ][a-zà-öø-ÿ])")
COLON_GLUE_RE = re.compile(r"(?<=[a-zà-öø-ÿ]):(?=[A-ZÀ-Þ])")
INVISIBLE_CHARS_RE = re.compile(r"[\u00ad\u200b\u200c\u200d\ufeff]")
GLUED_WORD_RE = re.compile(r"[A-Za-z]{8,}")

DEFAULT_PAGE_WIDTH = 612

MIN_DE_GLUE_PART = 3
MIN_DE_GLUE_FREQUENCY = 300

EXTRA_KNOWN_WORDS = frozenset({"wordpress", "postgres", "nodejs", "github"})


@lru_cache(maxsize=1)
def _known_words():
    spell = SpellChecker()
    words = set(EXTRA_KNOWN_WORDS)
    try:
        words.update(spell.word_frequency.keys())
    except Exception:
        pass
    words.update(SKILL_KEYWORDS)
    for aliases in SKILL_ALIASES.values():
        words.update(alias.lower() for alias in aliases)
    for display in DISPLAY_NAMES.values():
        words.update(part for part in re.split(r"[^a-z]+", display.lower()) if part)
    return words


@lru_cache(maxsize=1)
def _word_frequencies():
    try:
        spell = SpellChecker()
        return {
            word: spell.word_frequency[word] for word in spell.word_frequency.keys()
        }
    except Exception:
        return {}


def _is_known(word):
    return word in _known_words()


def _split_score(word, index):
    frequencies = _word_frequencies()
    left = word[:index].lower()
    right = word[index:].lower()
    if not _is_known(left) or not _is_known(right):
        return None
    if left not in frequencies or right not in frequencies:
        return None
    left_frequency = frequencies[left]
    right_frequency = frequencies[right]
    if (
        left_frequency < MIN_DE_GLUE_FREQUENCY
        or right_frequency < MIN_DE_GLUE_FREQUENCY
    ):
        return None
    return left_frequency * right_frequency


def _deglue_word(word):
    if _is_known(word.lower()):
        return word

    best_index = None
    best_score = None
    for index in range(MIN_DE_GLUE_PART, len(word) - MIN_DE_GLUE_PART + 1):
        score = _split_score(word, index)
        if score is not None and (best_score is None or score > best_score):
            best_index = index
            best_score = score

    if best_index is None:
        return word
    return word[:best_index] + " " + word[best_index:]


def normalize_extracted_text(text, deglue=False):
    text = INVISIBLE_CHARS_RE.sub("", text)
    text = COLON_GLUE_RE.sub(": ", text)
    text = PERIOD_GLUE_RE.sub(r"\1 ", text)
    if deglue:
        text = GLUED_WORD_RE.sub(lambda match: _deglue_word(match.group(0)), text)
    return text


def _extract_with_pypdf(file_bytes):
    reader = PdfReader(BytesIO(file_bytes))

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            return ""

    parts = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text.strip())

    return "\n".join(parts).strip()


def _extract_pages_with_pdfplumber(file_bytes):
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        return list(pdf.pages)


def extract_text_from_pdf_bytes(file_bytes: bytes) -> str:
    pypdf_text = ""
    try:
        pypdf_text = _extract_with_pypdf(file_bytes)
    except Exception:
        pypdf_text = ""

    try:
        pages = _extract_pages_with_pdfplumber(file_bytes)
    except Exception:
        return normalize_extracted_text(pypdf_text, deglue=True).strip()

    page_texts = []
    columnar = False
    plumber_words = 0

    try:
        for page in pages:
            width = page.width or DEFAULT_PAGE_WIDTH
            words = page.extract_words() or []
            plumber_words += len(words)

            if has_columnar_layout(words, width):
                columnar = True
                text = columnar_text(words, width)
            else:
                text = page.extract_text() or ""

            if text.strip():
                page_texts.append(text.strip())
    except Exception:
        return normalize_extracted_text(pypdf_text, deglue=True).strip()

    plumber_text = "\n".join(page_texts)
    pypdf_word_count = len(pypdf_text.split())

    if columnar and plumber_text:
        text = plumber_text
    elif plumber_words > pypdf_word_count * 1.05 and plumber_text:
        text = plumber_text
    else:
        text = pypdf_text or plumber_text

    return normalize_extracted_text(text, deglue=True).strip()


def extract_text_from_docx_bytes(file_bytes: bytes) -> str:
    try:
        document = Document(BytesIO(file_bytes))
    except Exception:
        return ""

    evidence = build_docx_evidence(document)
    parts = evidence["zone_lines"] + evidence["body_lines"]

    return normalize_extracted_text("\n".join(parts)).strip()
