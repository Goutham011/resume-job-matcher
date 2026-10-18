import re

HEADING_GROUPS = {
    "Summary": {
        "summary",
        "professional summary",
        "executive summary",
        "professional profile",
        "profile",
        "objective",
        "career objective",
        "about",
        "about me",
    },
    "Experience": {
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "employment history",
        "work history",
        "relevant experience",
        "professional background",
        "career history",
    },
    "Education": {
        "education",
        "academics",
        "academic background",
        "education & training",
    },
    "Skills": {
        "skills",
        "technical skills",
        "core skills",
        "key skills",
        "skills & tools",
        "skills and tools",
        "skills & interests",
        "technical skills & tools",
        "technologies",
        "tools",
        "core competencies",
        "competencies",
        "areas of expertise",
        "expertise",
        "technical proficiencies",
        "proficiencies",
        "skill set",
        "skillset",
    },
    "Projects": {
        "projects",
        "personal projects",
        "selected projects",
        "academic projects",
        "key projects",
        "notable projects",
        "technical projects",
        "selected work",
    },
    "Certifications": {
        "certifications",
        "certificates",
        "licenses",
        "training",
    },
    "Awards": {
        "awards",
        "achievements",
        "honors",
        "publications",
    },
    "Other": {
        "activities",
        "extracurricular",
        "extracurriculars",
        "leadership",
        "volunteer",
        "volunteering",
        "volunteer experience",
        "languages",
        "interests",
        "courses",
        "coursework",
        "relevant coursework",
        "volunteer work",
    },
}

REQUIRED_HEADINGS = ("Experience", "Education", "Skills")

_TITLE_BY_VARIANT = {}
for _title, _variants in HEADING_GROUPS.items():
    for _variant in _variants:
        _TITLE_BY_VARIANT[_variant] = _title

TRAILING_JUNK_RE = re.compile(r"[\s:;.,|•*—–\-]+$")
LEADING_JUNK_RE = re.compile(r"^[\s•*\-—–]+")
INLINE_CONTENT_RE = re.compile(r"\s+[—–|]\s+|:\s+")
CAPS_HEADING_RE = re.compile(r"[A-Z][A-Z\s&/,'\-]+")
MAX_HEADING_LENGTH = 60
MAX_CAPS_HEADING_LENGTH = 40


def normalize_heading_line(line):
    line = LEADING_JUNK_RE.sub("", line.strip())
    line = TRAILING_JUNK_RE.sub("", line)
    line = re.sub(r"\s+", " ", line)
    return line.lower()


def _title_for(normalized):
    return _TITLE_BY_VARIANT.get(normalized)


COMBINED_HEADING_SPLIT_RE = re.compile(r"\s*(?:&|/|,|\band\b|\+)\s*", re.IGNORECASE)


def match_headings(line):
    title = match_heading(line)
    if title:
        return [title]

    stripped = line.strip()
    if not stripped or len(stripped) > MAX_HEADING_LENGTH:
        return []

    parts = [part for part in COMBINED_HEADING_SPLIT_RE.split(stripped) if part.strip()]
    if len(parts) < 2:
        return []

    titles = []
    for part in parts:
        part_title = _title_for(normalize_heading_line(part))
        if not part_title:
            return []
        if part_title not in titles:
            titles.append(part_title)
    return titles


def match_heading(line):
    stripped = line.strip()
    if not stripped or len(stripped) > MAX_HEADING_LENGTH:
        return None

    normalized = normalize_heading_line(stripped)
    if not normalized:
        return None

    title = _title_for(normalized)
    if title:
        return title

    parts = INLINE_CONTENT_RE.split(stripped, maxsplit=1)
    if len(parts) == 2 and parts[1].strip():
        prefix = normalize_heading_line(parts[0])
        title = _title_for(prefix)
        if title:
            return title

    if (
        len(stripped) <= MAX_CAPS_HEADING_LENGTH
        and len(stripped.split()) <= 5
        and CAPS_HEADING_RE.fullmatch(stripped)
    ):
        cleaned = stripped.strip(": ").strip()
        canonical = _title_for(normalize_heading_line(cleaned))
        return canonical or cleaned

    return None
