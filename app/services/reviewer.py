import re

from spellchecker import SpellChecker

from app.services.contacts import EMAIL_RE, LINK_RE, looks_like_phone
from app.services.extractor import SKILL_KEYWORDS
from app.services.headings import REQUIRED_HEADINGS, match_headings
from app.services.keywords import count_term

_spell = None

COMMON_TYPOS = {
    "acheive": "achieve",
    "acheived": "achieved",
    "acheivement": "achievement",
    "adress": "address",
    "alot": "a lot",
    "applicaton": "application",
    "architechture": "architecture",
    "basicly": "basically",
    "becuase": "because",
    "buisness": "business",
    "commited": "committed",
    "comunication": "communication",
    "definately": "definitely",
    "developement": "development",
    "enviroment": "environment",
    "exprience": "experience",
    "experiance": "experience",
    "familar": "familiar",
    "finaly": "finally",
    "framwork": "framework",
    "futher": "further",
    "implementaion": "implementation",
    "independant": "independent",
    "langauge": "language",
    "maintainance": "maintenance",
    "managment": "management",
    "neccessary": "necessary",
    "occured": "occurred",
    "occurence": "occurrence",
    "perfomance": "performance",
    "posession": "possession",
    "profesional": "professional",
    "recieve": "receive",
    "recieved": "received",
    "recomend": "recommend",
    "refered": "referred",
    "responsibilty": "responsibility",
    "seperate": "separate",
    "sucess": "success",
    "sucessful": "successful",
    "successfull": "successful",
    "teh": "the",
    "thier": "their",
    "unecessary": "unnecessary",
    "wich": "which",
}

WEAK_PHRASES = {
    "responsible for": (
        "Start with a strong action verb instead, such as 'Managed', "
        "'Owned', or 'Led'."
    ),
    "worked on": "Use 'Built', 'Shipped', 'Delivered', or 'Launched'.",
    "helped with": "Use 'Drove', 'Supported', or 'Enabled', and add the outcome.",
    "assisted with": "Use 'Supported' or 'Partnered with', and add the outcome.",
    "in charge of": "Use 'Led' or 'Managed'.",
    "duties included": (
        "Start the bullet with an action verb such as 'Built', "
        "'Automated', or 'Analyzed'."
    ),
    "tasked with": "Use 'Owned' or 'Executed'.",
}

BUZZWORDS = [
    "team player",
    "hard worker",
    "hard-working",
    "detail oriented",
    "detail-oriented",
    "go getter",
    "go-getter",
    "self starter",
    "self-starter",
    "think outside the box",
    "results driven",
    "results-driven",
    "guru",
    "ninja",
    "rockstar",
    "synergy",
    "dynamic professional",
    "proven track record",
]

WHITELIST = {
    "agile",
    "api",
    "apis",
    "applicant",
    "backend",
    "backends",
    "backlog",
    "b2b",
    "b2c",
    "codebase",
    "codebases",
    "config",
    "configs",
    "devops",
    "docker",
    "frontend",
    "fullstack",
    "github",
    "gitlab",
    "golang",
    "graphql",
    "html",
    "http",
    "https",
    "javascript",
    "jira",
    "json",
    "kanban",
    "kubernetes",
    "linkedin",
    "linux",
    "llm",
    "llms",
    "microservice",
    "microservices",
    "mongodb",
    "mysql",
    "nodejs",
    "nosql",
    "npm",
    "observability",
    "postgres",
    "postgresql",
    "pytest",
    "redis",
    "repo",
    "repos",
    "restful",
    "resume",
    "roadmap",
    "roadmaps",
    "runtime",
    "runtimes",
    "saas",
    "scikit",
    "scrum",
    "serverless",
    "sql",
    "sqlite",
    "stakeholder",
    "stakeholders",
    "toolkit",
    "toolkits",
    "typescript",
    "unix",
    "uptime",
    "url",
    "urls",
    "uvicorn",
    "venv",
    "webhook",
    "webhooks",
    "workflow",
    "workflows",
}

for _keyword in SKILL_KEYWORDS:
    for _part in re.split(r"[^a-z]+", _keyword):
        if _part:
            WHITELIST.add(_part)

IMPACT_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:%|percent|million|billion|thousand|\+|x\b|k\b|m\b|bn\b)"
    r"|\$\s?\d|₹\s?\d|€\s?\d",
    re.IGNORECASE,
)

BULLET_MARKER_RE = re.compile(r"^[•●○▪◦‣·*>\-]+\s*")

CATEGORY_ORDER = {
    "spelling": 0,
    "grammar": 1,
    "punctuation": 2,
    "structure": 3,
    "style": 4,
}

MAX_SPELLING_FLAGS = 15
MAX_FLAG_PER_RULE = 3
ALL_CAPS_CORRECTION_FREQUENCY = 1000

ALL_CAPS_IGNORE = (
    WHITELIST
    | SKILL_KEYWORDS
    | {
        "oauth",
        "jwt",
        "sso",
        "nginx",
        "kafka",
        "grpc",
        "terraform",
        "ansible",
        "jenkins",
        "grafana",
        "prometheus",
        "yaml",
        "etl",
        "kpi",
        "roi",
        "csv",
        "xml",
        "css",
    }
)

A_EXCEPTIONS = {
    "unique",
    "university",
    "universal",
    "user",
    "users",
    "usage",
    "use",
    "using",
    "used",
    "unit",
    "units",
    "united",
    "usb",
    "ui",
    "ux",
    "utopia",
    "eulogy",
    "europe",
    "useful",
    "usual",
    "usually",
    "utility",
    "utilities",
    "european",
    "one",
    "once",
    "url",
    "urls",
    "unified",
    "uniform",
    "union",
    "unicode",
    "euro",
    "euros",
    "ukulele",
    "ubiquitous",
}

AN_EXCEPTIONS = {
    "hour",
    "hours",
    "honest",
    "honestly",
    "honor",
    "honors",
    "heir",
    "mba",
    "faq",
    "ssd",
    "sla",
    "sre",
    "sdk",
    "ide",
    "orm",
    "etl",
    "ai",
    "ml",
    "rl",
    "api",
    "aws",
    "sql",
    "http",
    "https",
    "html",
    "hr",
    "nft",
    "rpa",
    "fbi",
    "nfl",
    "nba",
    "mvp",
    "rpg",
    "sd",
    "ssl",
    "ssh",
    "xml",
}


def _get_spell():
    global _spell
    if _spell is None:
        _spell = SpellChecker()
    return _spell


def _snippet(text, start, end, pad=32):
    start = max(0, start - pad)
    end = min(len(text), end + pad)
    frag = re.sub(r"\s+", " ", text[start:end]).strip()
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{frag}{suffix}"


def _mask_contacts(text):
    masked = EMAIL_RE.sub(lambda m: " " * len(m.group(0)), text)
    masked = re.sub(r"https?://\S+|www\.\S+", lambda m: " " * len(m.group(0)), masked)
    return re.sub(
        r"\b[\w-]+\.(?:com|org|net|io|dev|ai|me|co|in|app|xyz|info|biz)(?:/\S*)?",
        lambda m: " " * len(m.group(0)),
        masked,
        flags=re.IGNORECASE,
    )


def _issue(category, message, suggestion=None, snippet=None):
    return {
        "category": category,
        "message": message,
        "suggestion": suggestion,
        "snippet": snippet,
    }


def _split_sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def _strip_bullet_marker(line):
    return BULLET_MARKER_RE.sub("", line).strip()


def _looks_like_contact_line(line):
    if EMAIL_RE.search(line) or looks_like_phone(line):
        return True
    return bool(LINK_RE.search(line))


def _logical_lines(text):
    units = []
    buffer = ""

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if buffer:
                units.append(buffer)
                buffer = ""
            continue

        if BULLET_MARKER_RE.match(line):
            if buffer:
                units.append(buffer)
            buffer = line
        elif (
            buffer
            and line[0].islower()
            and not re.search(r"[.!?]$", buffer)
            and not _looks_like_contact_line(line)
            and not _looks_like_contact_line(buffer)
        ):
            buffer = f"{buffer} {line}"
        else:
            if buffer:
                units.append(buffer)
            buffer = line

    if buffer:
        units.append(buffer)

    return units


def _find_spelling_issues(text):
    issues = []
    lowered = text.lower()

    for typo, correction in COMMON_TYPOS.items():
        match = re.search(rf"(?<!\w){re.escape(typo)}(?!\w)", lowered)
        if match:
            original = text[match.start() : match.end()]
            issues.append(
                _issue(
                    "spelling",
                    f"'{original}' appears to be misspelled.",
                    f"Change it to '{correction}'.",
                    _snippet(text, match.start(), match.end()),
                )
            )

    spell = _get_spell()
    masked = _mask_contacts(text)
    seen = set()
    flagged = 0

    for match in re.finditer(r"\b[a-z]{4,}\b", masked):
        word = match.group(0)
        if (
            word in seen
            or word in COMMON_TYPOS
            or word in WHITELIST
            or not spell.unknown([word])
        ):
            continue

        seen.add(word)
        flagged += 1
        if flagged > MAX_SPELLING_FLAGS:
            break

        correction = spell.correction(word)
        if correction and correction != word:
            suggestion = (
                f"Did you mean '{correction}'? "
                "If it is a name or product, you can ignore this."
            )
        else:
            suggestion = "Double-check this word; it is not a standard word."

        issues.append(
            _issue(
                "spelling",
                f"'{word}' may be misspelled.",
                suggestion,
                _snippet(text, match.start(), match.end()),
            )
        )

    for match in re.finditer(r"\b[A-Z]{4,}\b", masked):
        original = match.group(0)
        word = original.lower()
        if (
            word in seen
            or word in COMMON_TYPOS
            or word in ALL_CAPS_IGNORE
            or not spell.unknown([word])
        ):
            continue

        correction = spell.correction(word)
        if not correction or correction == word:
            continue
        if (
            correction not in spell.word_frequency
            or spell.word_frequency[correction] < ALL_CAPS_CORRECTION_FREQUENCY
        ):
            continue

        seen.add(word)
        flagged += 1
        if flagged > MAX_SPELLING_FLAGS:
            break

        issues.append(
            _issue(
                "spelling",
                f"'{original}' may be misspelled.",
                f"Did you mean '{correction}'? "
                "If it is a name or product, you can ignore this.",
                _snippet(text, match.start(), match.end()),
            )
        )

    return issues


def _find_grammar_issues(text):
    issues = []

    for match in re.finditer(r"\b(\w{3,})\s+\1\b", text, re.IGNORECASE):
        issues.append(
            _issue(
                "grammar",
                f"The word '{match.group(1)}' is repeated.",
                "Remove the duplicate word.",
                _snippet(text, match.start(), match.end()),
            )
        )

    for match in list(re.finditer(r"(?<![\w'.])i(?![\w'.])", text))[:MAX_FLAG_PER_RULE]:
        issues.append(
            _issue(
                "grammar",
                "Lowercase 'i' is used as the pronoun.",
                "Use a capital 'I'.",
                _snippet(text, match.start(), match.end()),
            )
        )

    flagged = 0
    for match in re.finditer(r"\ba\s+([aeiou]\w*)", text, re.IGNORECASE):
        word = match.group(1)
        if word.lower().rstrip("s") in A_EXCEPTIONS:
            continue
        flagged += 1
        if flagged > MAX_FLAG_PER_RULE:
            break
        issues.append(
            _issue(
                "grammar",
                f"Use 'an' before '{word}': '{match.group(0)}'.",
                f"Write 'an {word}'.",
                _snippet(text, match.start(), match.end()),
            )
        )

    flagged = 0
    for match in re.finditer(
        r"\ban\s+([bcdfghjklmnpqrstvwxyz]\w*)", text, re.IGNORECASE
    ):
        word = match.group(1)
        if word.lower().rstrip("s") in AN_EXCEPTIONS:
            continue
        flagged += 1
        if flagged > MAX_FLAG_PER_RULE:
            break
        issues.append(
            _issue(
                "grammar",
                f"Use 'a' before '{word}': '{match.group(0)}'.",
                f"Write 'a {word}'.",
                _snippet(text, match.start(), match.end()),
            )
        )

    passive = list(
        re.finditer(
            r"\b(?:was|were|is|are|been|being|be)\s+\w+(?:ed|en)\b",
            text,
            re.IGNORECASE,
        )
    )
    for match in passive[:2]:
        issues.append(
            _issue(
                "grammar",
                f"Possible passive voice: '{match.group(0)}'.",
                "Prefer active voice, e.g. 'Built the service' "
                "instead of 'The service was built'.",
                _snippet(text, match.start(), match.end()),
            )
        )

    flagged = 0
    for segment in _logical_lines(text):
        stripped = _strip_bullet_marker(segment)
        if len(stripped.split()) < 3:
            continue
        if _looks_like_contact_line(segment):
            continue
        if stripped and stripped[0].islower():
            flagged += 1
            if flagged > MAX_FLAG_PER_RULE:
                break
            issues.append(
                _issue(
                    "grammar",
                    f"Line starts with a lowercase letter: '{stripped[:50]}'.",
                    "Capitalize the first letter.",
                    stripped[:70],
                )
            )

    return issues


def _find_punctuation_issues(text):
    issues = []

    for match in list(re.finditer(r"\S {2,}\S", text))[:2]:
        issues.append(
            _issue(
                "punctuation",
                "Double space between words.",
                "Use a single space.",
                _snippet(text, match.start(), match.end()),
            )
        )

    for match in list(re.finditer(r"\S[ \t]+[,.!?;:]", text))[:2]:
        issues.append(
            _issue(
                "punctuation",
                f"Space before punctuation ('{match.group(0).strip()}').",
                "Remove the space before the punctuation mark.",
                _snippet(text, match.start(), match.end()),
            )
        )

    for match in list(re.finditer(r"[,;:](?=[A-Za-z])", text))[:MAX_FLAG_PER_RULE]:
        issues.append(
            _issue(
                "punctuation",
                f"Missing space after '{match.group(0)}'.",
                "Add a space after the punctuation mark.",
                _snippet(text, match.start(), match.end()),
            )
        )

    for match in list(re.finditer(r"([,;!?])\1+", text))[:2]:
        issues.append(
            _issue(
                "punctuation",
                f"Repeated punctuation ('{match.group(0)}').",
                "Use a single punctuation mark.",
                _snippet(text, match.start(), match.end()),
            )
        )

    for line in text.splitlines():
        if line.count("(") != line.count(")"):
            issues.append(
                _issue(
                    "punctuation",
                    "Unbalanced parentheses in a line.",
                    "Check that every '(' has a matching ')'.",
                    line.strip()[:70],
                )
            )
            break

    bullet_lines = [
        _strip_bullet_marker(unit)
        for unit in _logical_lines(text)
        if BULLET_MARKER_RE.match(unit)
    ]
    bullet_lines = [line for line in bullet_lines if len(line.split()) >= 5]
    if len(bullet_lines) >= 4:
        ends = [line[-1] in ".!?" for line in bullet_lines]
        with_end = sum(ends)
        without = len(ends) - with_end
        minority = min(with_end, without)
        if minority >= 2 and minority / len(ends) >= 0.25:
            issues.append(
                _issue(
                    "punctuation",
                    "Bullets mix ending punctuation "
                    f"({without} bullets without a period, {with_end} with one).",
                    "Pick one style and stay consistent.",
                    None,
                )
            )

    return issues


def _find_structure_issues(text):
    issues = []
    word_count = len(text.split())

    if word_count < 150:
        issues.append(
            _issue(
                "structure",
                f"Your resume looks short (about {word_count} words).",
                "Aim for a focused 1-2 page resume with details on your results.",
                None,
            )
        )
    elif word_count > 1100:
        issues.append(
            _issue(
                "structure",
                f"Your resume looks long (about {word_count} words).",
                "Trim to the most relevant 1-2 pages.",
                None,
            )
        )

    if not EMAIL_RE.search(text):
        issues.append(
            _issue(
                "structure",
                "No email address was found.",
                "Add a professional email at the top of the resume.",
                None,
            )
        )

    phone_found = looks_like_phone(text)
    if not phone_found:
        issues.append(
            _issue(
                "structure",
                "No phone number was found.",
                "Add a phone number recruiters can reach you on.",
                None,
            )
        )

    if not re.search(r"linkedin\.com", text, re.IGNORECASE):
        issues.append(
            _issue(
                "structure",
                "No LinkedIn profile was found.",
                "Add your LinkedIn URL so recruiters can learn more.",
                None,
            )
        )

    lowered = text.lower()
    found_sections = set()
    for line in text.splitlines():
        for title in match_headings(line):
            found_sections.add(title)
    for section in REQUIRED_HEADINGS:
        if section in found_sections:
            continue
        if section.lower() in lowered:
            continue
        issues.append(
            _issue(
                "structure",
                f"No '{section}' section was found.",
                f"Add a clearly labeled '{section}' section "
                "so keyword scans and recruiters can find it.",
                None,
            )
        )

    return issues


def _find_style_issues(text):
    issues = []
    lowered = text.lower()

    for phrase, fix in WEAK_PHRASES.items():
        match = re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", lowered)
        if match:
            issues.append(
                _issue(
                    "style",
                    f"Weak phrase: '{phrase}'.",
                    fix,
                    _snippet(text, match.start(), match.end()),
                )
            )

    for phrase in BUZZWORDS:
        match = re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", lowered)
        if match:
            issues.append(
                _issue(
                    "style",
                    f"Cliché phrase: '{phrase}'.",
                    "Replace it with a concrete, measurable achievement.",
                    _snippet(text, match.start(), match.end()),
                )
            )

    pronouns = list(re.finditer(r"\b(I|me|my|mine|myself)\b", text))
    if pronouns:
        issues.append(
            _issue(
                "style",
                f"First-person pronouns found ({len(pronouns)} times, "
                f"e.g. '{pronouns[0].group(0)}').",
                "Resumes read stronger without 'I' or 'my' - "
                "start bullets with action verbs.",
                _snippet(text, pronouns[0].start(), pronouns[0].end()),
            )
        )

    flagged = 0
    for segment in _split_sentences(text):
        words = segment.split()
        if len(words) > 35:
            flagged += 1
            if flagged > 2:
                break
            issues.append(
                _issue(
                    "style",
                    f"Very long sentence ({len(words)} words).",
                    "Split it into two shorter sentences.",
                    " ".join(words[:12]) + "...",
                )
            )

    return issues


def analyze_resume(text, jd_text=None, jd_skills=None):
    issues = (
        _find_spelling_issues(text)
        + _find_grammar_issues(text)
        + _find_punctuation_issues(text)
        + _find_structure_issues(text)
        + _find_style_issues(text)
    )

    if jd_text and jd_skills:
        issues.extend(find_stuffing_issues(text, jd_skills, jd_text))

    seen = set()
    deduped = []
    for issue in issues:
        key = (issue["category"], issue["message"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)

    deduped.sort(key=lambda issue: CATEGORY_ORDER.get(issue["category"], 9))
    return deduped


def count_skill_mentions(text, skills):
    return {skill: count_term(skill, text) for skill in skills}


STUFF_MIN_COUNT = 12
STUFF_RATIO = 10
MAX_STUFF_FLAGS = 3


def find_stuffing_issues(resume_text, jd_skills, jd_text):
    issues = []

    for skill in jd_skills:
        resume_count = count_term(skill, resume_text)
        if resume_count < STUFF_MIN_COUNT:
            continue

        jd_count = count_term(skill, jd_text)
        if resume_count <= max(jd_count, 1) * STUFF_RATIO:
            continue

        issues.append(
            _issue(
                "style",
                f"'{skill}' appears about {resume_count} times in your resume "
                f"but only {jd_count} times in the posting.",
                "This can look like keyword stuffing to recruiters and some "
                "scanners. Keep each skill to a few natural mentions in real "
                "achievements.",
                None,
            )
        )
        if len(issues) >= MAX_STUFF_FLAGS:
            break

    return issues


def build_recommendations(
    resume_text,
    jd_text,
    matched_skills,
    missing_skills,
    breakdown,
    skill_mentions,
    issues,
    mirrored=False,
    paraphrased=False,
):
    recs = []
    jd_skill_total = len(matched_skills) + len(missing_skills)

    if paraphrased and not mirrored:
        recs.append(
            {
                "priority": "high",
                "title": "Rework sections that follow the posting too closely",
                "detail": (
                    "Several parts of your resume restate the posting sentence "
                    "by sentence in different words. Recruiters may read this as "
                    "copied content. Rebuild those sections around your own "
                    "projects, metrics, and outcomes."
                ),
            }
        )

    if mirrored:
        recs.append(
            {
                "priority": "high",
                "title": "Replace wording copied from the posting",
                "detail": (
                    "Much of your resume matches the job posting word-for-word. "
                    "Recruiters and plagiarism checks can flag this. Rewrite "
                    "each bullet in your own words, keep your real achievements, "
                    "and reuse only the specific tool and role names."
                ),
            }
        )

    if missing_skills and jd_skill_total:
        ordered = sorted(missing_skills, key=lambda s: (-skill_mentions.get(s, 0), s))
        named = ", ".join(
            (
                f"{skill} ({skill_mentions.get(skill, 0)}x)"
                if skill_mentions.get(skill, 0) > 1
                else skill
            )
            for skill in ordered[:5]
        )
        gain = round(
            breakdown["skill_weight"] * (100 - breakdown["skill_coverage"]) / 100, 1
        )
        recs.append(
            {
                "priority": "high",
                "title": (
                    f"Add the {len(missing_skills)} missing skill(s) "
                    "the job asks for"
                ),
                "detail": (
                    f"The posting mentions: {named}. If you genuinely have "
                    "these skills, add them to a 'Skills' section and show "
                    "them in experience bullets - for example: 'Deployed and "
                    "scaled services on Kubernetes'. Skills are "
                    f"{breakdown['skill_weight']}% of your score and you "
                    f"currently cover {breakdown['skill_coverage']}% - closing "
                    f"this gap could add about {gain} points."
                ),
            }
        )

    if breakdown["content_similarity"] < 70 and not mirrored and not paraphrased:
        priority = "high" if breakdown["content_similarity"] < 50 else "medium"
        recs.append(
            {
                "priority": priority,
                "title": "Use the posting's vocabulary for your own work",
                "detail": (
                    "Your resume's overall wording overlaps only "
                    f"{breakdown['content_similarity']}% with the posting. "
                    "Describe your actual experience using the posting's exact "
                    "job title, tool names, and key terms where they are "
                    "accurate for you - in your own sentences, not copied "
                    "phrasing. This language match drives "
                    f"{breakdown['content_weight']}% of your score."
                ),
            }
        )

    fixable = [
        issue
        for issue in issues
        if issue["category"] in {"spelling", "grammar", "punctuation"}
    ]
    if fixable:
        recs.append(
            {
                "priority": "high" if len(fixable) >= 5 else "medium",
                "title": (
                    f"Fix {len(fixable)} spelling, grammar, or " "punctuation issue(s)"
                ),
                "detail": (
                    "Many recruiters reject resumes over typos. See the "
                    "writing check above - every issue shows the exact text "
                    "and how to fix it."
                ),
            }
        )

    basics = [
        issue
        for issue in issues
        if issue["category"] == "structure"
        and issue["message"].startswith(("No email", "No phone", "No LinkedIn", "No '"))
    ]
    if basics:
        problems = "; ".join(issue["message"].rstrip(".") for issue in basics[:3])
        recs.append(
            {
                "priority": "medium",
                "title": "Complete the basics of your resume",
                "detail": (
                    f"{problems}. Recruiters and resume-scanning software "
                    "look for these first."
                ),
            }
        )

    weak_phrases = [
        issue
        for issue in issues
        if issue["category"] == "style" and issue["message"].startswith("Weak phrase")
    ]
    pronouns = [
        issue
        for issue in issues
        if issue["category"] == "style" and issue["message"].startswith("First-person")
    ]
    if weak_phrases or pronouns:
        if weak_phrases and pronouns:
            detail = (
                "Phrases like 'responsible for' and 'worked on' sound "
                "passive, and first-person pronouns weaken bullets. Swap "
                "them for strong action verbs and add the result you "
                "achieved."
            )
        elif weak_phrases:
            detail = (
                "Phrases like 'responsible for' and 'worked on' sound "
                "passive. Swap them for strong action verbs and add the "
                "result you achieved."
            )
        else:
            detail = (
                "Resumes read stronger without 'I' or 'my'. Start each "
                "bullet with a strong action verb such as 'Built' or 'Led'."
            )
        recs.append(
            {
                "priority": "medium",
                "title": "Replace weak or filler phrases",
                "detail": detail,
            }
        )

    if len(IMPACT_RE.findall(resume_text)) < 2:
        recs.append(
            {
                "priority": "medium",
                "title": "Quantify your impact with numbers",
                "detail": (
                    "Add measurable results, e.g. 'reduced API latency by "
                    "40%', 'managed a $50k budget', or 'served 10k users'. "
                    "Numbers make achievements concrete for recruiters."
                ),
            }
        )

    word_count = len(resume_text.split())
    if word_count < 150:
        recs.append(
            {
                "priority": "medium",
                "title": "Add more detail to your resume",
                "detail": (
                    "More relevant detail gives both recruiters and the "
                    "matcher a fuller picture. Cover each role with 3-5 "
                    "result-focused bullets."
                ),
            }
        )
    elif word_count > 1100:
        recs.append(
            {
                "priority": "low",
                "title": "Tighten your resume length",
                "detail": (
                    "Trim older or less relevant content so the strongest "
                    "material fits in 1-2 pages."
                ),
            }
        )

    recs.sort(key=lambda rec: {"high": 0, "medium": 1, "low": 2}[rec["priority"]])

    if not recs:
        recs = [
            {
                "priority": "low",
                "title": "Your resume is in great shape",
                "detail": (
                    "No major issues found. Keep the skills section near the "
                    "top so scanning tools pick it up quickly."
                ),
            }
        ]

    return recs[:6]
