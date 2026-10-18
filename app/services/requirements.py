import re
from datetime import datetime

MUST_MARKERS = [
    "must have",
    "must be",
    "required",
    "requirement",
    "minimum",
    "need to",
    "essential",
    "mandatory",
    "strong background",
]

PREFERRED_MARKERS = [
    "preferred",
    "a plus",
    "nice to have",
    "desirable",
    "ideally",
    "advantage",
    "bonus",
    "familiarity with",
]

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

MONTH_PATTERN = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+"

DATE_RANGE_RE = re.compile(
    rf"(?:({MONTH_PATTERN.rstrip()})?\s*)?(19\d{{2}}|20\d{{2}})"
    rf"\s*(?:--|-|–|—|to)\s*"
    rf"(?:({MONTH_PATTERN.rstrip()})?\s*)?"
    rf"(19\d{{2}}|20\d{{2}}|present|current|now|today|ongoing)",
    re.IGNORECASE,
)

YEARS_REQUIREMENT_PATTERNS = [
    re.compile(
        r"(\d+)\s*(?:-|–|—|to)\s*\d+\s*\+?\s*(?:years?|yrs?)"
        r"[^.!?\n]{0,40}?\bexperience\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:at least|minimum(?:\s+of)?|min\.?)\s*(\d+)\s*\+?\s*" r"(?:years?|yrs?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(\d+)\s*\+?\s*(?:years?|yrs?)[^.!?\n]{0,40}?\bexperience\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bexperience\b[^.!?\n]{0,30}?(\d+)\s*\+?\s*(?:years?|yrs?)",
        re.IGNORECASE,
    ),
]

EXCLUDED_EXPERIENCE_SECTIONS = {"Education", "Projects", "Certifications", "Awards"}

DEGREE_RE = re.compile(
    r"\b(bachelor|master|b\.?s\.?|b\.?tech|m\.?s\.?|m\.?tech|mba|ph\.?d|doctorate)\b",
    re.IGNORECASE,
)

AUTHORIZATION_RE = re.compile(
    r"authoriz|sponsor|visa|citizen|permanent resident|work permit|green card",
    re.IGNORECASE,
)

LOCATION_RE = re.compile(r"on-?site|hybrid|in-?office|relocat", re.IGNORECASE)


def _split_sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def _clean_sentence(sentence):
    return re.sub(r"^[\s•\-\*\u2022>]+", "", sentence).strip()


def find_years_requirement(text):
    for pattern in YEARS_REQUIREMENT_PATTERNS:
        match = pattern.search(text)
        if match:
            return int(match.group(1))
    return None


def _experience_text(resume_text):
    from app.services.headings import match_headings

    buckets = {}
    current = None
    for line in resume_text.splitlines():
        titles = match_headings(line)
        if titles:
            current = titles[0]
            buckets.setdefault(current, [])
            continue
        buckets.setdefault(current, []).append(line)

    if "Experience" in buckets:
        return "\n".join(buckets.get(None, []) + buckets["Experience"])

    parts = []
    for section, lines in buckets.items():
        if section in EXCLUDED_EXPERIENCE_SECTIONS:
            continue
        parts.extend(lines)
    return "\n".join(parts)


def extract_requirements(jd_text):
    must_have = []
    preferred = []

    for sentence in _split_sentences(jd_text):
        cleaned = _clean_sentence(sentence)
        words = cleaned.split()
        if not 3 <= len(words) <= 45:
            continue

        lowered = cleaned.lower()
        if any(marker in lowered for marker in PREFERRED_MARKERS):
            if cleaned not in preferred and len(preferred) < 6:
                preferred.append(cleaned)
        elif (
            any(marker in lowered for marker in MUST_MARKERS)
            or find_years_requirement(cleaned) is not None
        ):
            if cleaned not in must_have and len(must_have) < 8:
                must_have.append(cleaned)

    return {"must_have": must_have, "preferred": preferred}


def _month_fraction(month_name, fallback):
    if not month_name:
        return fallback
    return (MONTHS.get(month_name[:3].lower(), fallback + 1) - 1) / 12


def estimate_experience_years(resume_text):
    now = datetime.now()
    now_fraction = now.year + (now.month - 1) / 12

    experience_text = _experience_text(resume_text)

    intervals = []
    for match in DATE_RANGE_RE.finditer(experience_text):
        start_month, start_year, end_month, end_value = match.groups()
        start = int(start_year) + _month_fraction(start_month, 0)

        if end_value.isdigit():
            end = int(end_value) + _month_fraction(end_month, 11)
        else:
            end = now_fraction

        if start > now_fraction + 1:
            continue
        end = min(end, now_fraction)

        if end < start:
            start, end = end, start
        if end - start >= 0.25:
            intervals.append((start, end))

    intervals.sort()
    merged = []
    for start, end in intervals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    dated_years = sum(end - start for start, end in merged)

    mentioned = re.search(
        r"(\d+(?:\.\d+)?)\+?\s*years?", experience_text, re.IGNORECASE
    )
    mentioned_years = min(float(mentioned.group(1)), 40.0) if mentioned else 0.0

    years = max(dated_years, mentioned_years)
    if years <= 0:
        return {"years": None, "source": "none"}

    source = "date ranges" if dated_years >= mentioned_years else "experience statement"
    return {"years": round(years, 1), "source": source}


def check_knockouts(jd_text, resume_text, years_estimate):
    checks = []
    lowered_jd = jd_text.lower()
    lowered_resume = resume_text.lower()

    years_required = find_years_requirement(jd_text)
    if years_required is not None:
        required = years_required
        estimated = years_estimate.get("years")
        jd_says = f"asks for about {required}+ years of experience"
        if estimated is None:
            checks.append(
                {
                    "topic": "Years of experience",
                    "jd_says": jd_says,
                    "resume_says": "no clear years could be estimated from the resume",
                    "status": "check",
                    "advice": "Add clear date ranges (e.g. 'Mar 2021 - Present') to "
                    "each role so screeners can count your years.",
                }
            )
        elif estimated >= required:
            checks.append(
                {
                    "topic": "Years of experience",
                    "jd_says": jd_says,
                    "resume_says": f"your resume shows about {estimated} years",
                    "status": "match",
                    "advice": "You meet the years requirement.",
                }
            )
        else:
            gap = round(required - estimated, 1)
            checks.append(
                {
                    "topic": "Years of experience",
                    "jd_says": jd_says,
                    "resume_says": f"your resume shows about {estimated} years",
                    "status": "possible_gap",
                    "advice": f"You appear to be about {gap} years short. Highlight "
                    "internships, relevant projects, or earlier dated roles honestly "
                    "to close the gap.",
                }
            )

    if DEGREE_RE.search(lowered_jd):
        if DEGREE_RE.search(lowered_resume):
            checks.append(
                {
                    "topic": "Degree",
                    "jd_says": "mentions a degree requirement",
                    "resume_says": "a degree is mentioned in your resume",
                    "status": "match",
                    "advice": "Your degree is visible - keep it near the top of the "
                    "Education section.",
                }
            )
        else:
            checks.append(
                {
                    "topic": "Degree",
                    "jd_says": "mentions a degree requirement",
                    "resume_says": "no degree was found",
                    "status": "check",
                    "advice": "If you hold a degree, add it with the graduation year. "
                    "If not, this can be a hard requirement at some companies.",
                }
            )

    if re.search(r"certif", lowered_jd):
        if re.search(r"certif", lowered_resume):
            checks.append(
                {
                    "topic": "Certification",
                    "jd_says": "mentions a certification",
                    "resume_says": "a certification is mentioned in your resume",
                    "status": "match",
                    "advice": "List certifications with the issuer and year.",
                }
            )
        else:
            checks.append(
                {
                    "topic": "Certification",
                    "jd_says": "mentions a certification",
                    "resume_says": "no certification was found",
                    "status": "check",
                    "advice": "If you hold a relevant certification, add it. If it is "
                    "required and you don't have it, consider this a gap to plan for.",
                }
            )

    if AUTHORIZATION_RE.search(lowered_jd):
        checks.append(
            {
                "topic": "Work authorization",
                "jd_says": "mentions work authorization or sponsorship",
                "resume_says": "not covered by a resume",
                "status": "info",
                "advice": "This is almost always asked in the application form, not "
                "read from your resume. Answer it honestly; if you need sponsorship "
                "and the posting rules it out, it is a hard stop.",
            }
        )

    if LOCATION_RE.search(lowered_jd):
        checks.append(
            {
                "topic": "Location / work arrangement",
                "jd_says": "mentions on-site, hybrid, or relocation",
                "resume_says": "not covered by a resume",
                "status": "info",
                "advice": "Apply only if the location and arrangement work for you; "
                "recruiters screen on this early.",
            }
        )

    return checks
