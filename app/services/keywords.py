import json
import math
import os
import re
from collections import Counter
from pathlib import Path

SKILL_ALIASES = {
    "kubernetes": ["k8s"],
    "machine learning": ["ml"],
    "deep learning": ["dl"],
    "nlp": ["natural language processing"],
    "postgresql": ["postgres"],
    "javascript": ["js"],
    "typescript": ["ts"],
    "node.js": ["nodejs", "node js"],
    "aws": ["amazon web services"],
    "gcp": ["google cloud", "google cloud platform"],
    "azure": ["microsoft azure"],
    "event planning": ["event management", "event coordination"],
    "community engagement": ["community outreach"],
    "seo": ["search engine optimization"],
    "sem": ["search engine marketing"],
    "crm": ["customer relationship management"],
    "data visualization": ["data visualisation"],
    "excel": ["microsoft excel", "ms excel"],
    "power bi": ["powerbi"],
    "communication": ["communication skills"],
    "leadership": ["leadership skills"],
    "collaboration": ["collaboration skills"],
    "teamwork": ["team work"],
    "problem solving": ["problem-solving", "problem solving skills"],
    "time management": ["time-management"],
    "critical thinking": ["critical-thinking"],
    "public speaking": ["public-speaking"],
    "decision making": ["decision-making"],
    "conflict resolution": ["conflict-resolution"],
    "mentoring": ["mentorship", "mentored"],
}

DISPLAY_NAMES = {
    "python": "Python",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "sql": "SQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "sqlite": "SQLite",
    "pandas": "pandas",
    "numpy": "NumPy",
    "scikit-learn": "scikit-learn",
    "machine learning": "Machine Learning",
    "deep learning": "Deep Learning",
    "nlp": "NLP",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
    "git": "Git",
    "github": "GitHub",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "react": "React",
    "node.js": "Node.js",
    "linux": "Linux",
    "rest api": "REST API",
    "graphql": "GraphQL",
    "data analysis": "data analysis",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "llm": "LLM",
    "rag": "RAG",
    "marketing": "Marketing",
    "digital marketing": "Digital Marketing",
    "growth marketing": "Growth Marketing",
    "product marketing": "Product Marketing",
    "content strategy": "Content Strategy",
    "content creation": "Content Creation",
    "social media": "Social Media",
    "publicity": "Publicity",
    "public relations": "Public Relations",
    "event planning": "Event Planning",
    "community engagement": "Community Engagement",
    "community building": "Community Building",
    "audience outreach": "Audience Outreach",
    "market research": "Market Research",
    "competitive research": "Competitive Research",
    "campaign management": "Campaign Management",
    "branding": "Branding",
    "copywriting": "Copywriting",
    "seo": "SEO",
    "sem": "SEM",
    "email marketing": "Email Marketing",
    "google analytics": "Google Analytics",
    "data visualization": "Data Visualization",
    "excel": "Excel",
    "power bi": "Power BI",
    "tableau": "Tableau",
    "crm": "CRM",
    "salesforce": "Salesforce",
    "hubspot": "HubSpot",
    "canva": "Canva",
    "figma": "Figma",
    "project management": "Project Management",
    "stakeholder management": "Stakeholder Management",
    "team coordination": "Team Coordination",
    "budget management": "Budget Management",
    "negotiation": "Negotiation",
    "customer service": "Customer Service",
    "communication": "Communication",
    "leadership": "Leadership",
    "collaboration": "Collaboration",
    "teamwork": "Teamwork",
    "problem solving": "Problem Solving",
    "time management": "Time Management",
    "adaptability": "Adaptability",
    "critical thinking": "Critical Thinking",
    "attention to detail": "Attention to Detail",
    "public speaking": "Public Speaking",
    "mentoring": "Mentoring",
    "ownership": "Ownership",
    "creativity": "Creativity",
    "decision making": "Decision Making",
    "conflict resolution": "Conflict Resolution",
}

CASE_SENSITIVE_SPELLINGS = {
    "excel": ["Excel"],
    "sem": ["SEM"],
    "ml": ["ML"],
    "dl": ["DL"],
    "ts": ["TS"],
}

SOFT_SKILLS = frozenset(
    {
        "communication",
        "leadership",
        "collaboration",
        "teamwork",
        "problem solving",
        "time management",
        "adaptability",
        "critical thinking",
        "attention to detail",
        "public speaking",
        "mentoring",
        "ownership",
        "creativity",
        "decision making",
        "conflict resolution",
    }
)

SKILL_KEYWORDS = {
    "python",
    "fastapi",
    "django",
    "flask",
    "sql",
    "postgresql",
    "mysql",
    "sqlite",
    "pandas",
    "numpy",
    "scikit-learn",
    "machine learning",
    "deep learning",
    "nlp",
    "docker",
    "kubernetes",
    "aws",
    "gcp",
    "azure",
    "git",
    "github",
    "javascript",
    "typescript",
    "react",
    "node.js",
    "linux",
    "rest api",
    "graphql",
    "data analysis",
    "tensorflow",
    "pytorch",
    "llm",
    "rag",
    "marketing",
    "digital marketing",
    "growth marketing",
    "product marketing",
    "content strategy",
    "content creation",
    "social media",
    "publicity",
    "public relations",
    "event planning",
    "community engagement",
    "community building",
    "audience outreach",
    "market research",
    "competitive research",
    "campaign management",
    "branding",
    "copywriting",
    "seo",
    "sem",
    "email marketing",
    "google analytics",
    "data visualization",
    "excel",
    "power bi",
    "tableau",
    "crm",
    "salesforce",
    "hubspot",
    "canva",
    "figma",
    "project management",
    "stakeholder management",
    "team coordination",
    "budget management",
    "negotiation",
    "customer service",
} | set(SOFT_SKILLS)

DEFAULT_SKILL_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "skills.json"
)


def load_skill_config(path=None):
    explicit = True
    if path is None:
        env_path = os.environ.get("SKILL_CONFIG_PATH")
        explicit = bool(env_path)
        path = env_path or DEFAULT_SKILL_CONFIG_PATH
    config_path = Path(path)
    if not config_path.exists():
        if explicit:
            raise RuntimeError(
                f"SKILL_CONFIG_PATH points to '{config_path}', which does not "
                "exist. Fix the path or unset SKILL_CONFIG_PATH."
            )
        return {}

    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(
            f"Skill configuration at '{config_path}' is not valid JSON: {exc}. "
            "Fix the file or unset SKILL_CONFIG_PATH."
        ) from exc

    skills = raw.get("skills") if isinstance(raw, dict) else None
    if not isinstance(skills, dict):
        raise RuntimeError(
            f"Skill configuration at '{config_path}' must be an object with a "
            "'skills' object. Fix the file or unset SKILL_CONFIG_PATH."
        )

    validated = {}
    for name, entry in skills.items():
        if not isinstance(name, str) or not name.strip():
            raise RuntimeError(
                f"Skill configuration has an invalid skill name: {name!r}"
            )
        name = name.strip().lower()
        if not isinstance(entry, dict):
            raise RuntimeError(f"Skill '{name}' must map to an object entry.")
        aliases = entry.get("aliases", [])
        if not isinstance(aliases, list) or not all(
            isinstance(alias, str) and alias.strip() for alias in aliases
        ):
            raise RuntimeError(f"Skill '{name}' has invalid aliases; expected strings.")
        kind = entry.get("kind", "hard")
        if kind not in {"hard", "soft"}:
            raise RuntimeError(f"Skill '{name}' has invalid kind '{kind}'.")
        display = entry.get("display", name)
        if not isinstance(display, str) or not display.strip():
            raise RuntimeError(f"Skill '{name}' has an invalid display name.")
        validated[name] = {
            "aliases": [alias.strip().lower() for alias in aliases],
            "kind": kind,
            "display": display.strip(),
        }
    return validated


def _apply_skill_config(config):
    soft = set(SOFT_SKILLS)
    for name, entry in config.items():
        SKILL_KEYWORDS.add(name)
        DISPLAY_NAMES.setdefault(name, entry["display"])
        if entry["kind"] == "soft":
            soft.add(name)
        aliases = entry["aliases"]
        if aliases:
            existing = list(SKILL_ALIASES.get(name, []))
            for alias in aliases:
                if alias not in existing:
                    existing.append(alias)
            SKILL_ALIASES[name] = existing
    return frozenset(soft)


SKILL_CONFIG = load_skill_config()
SOFT_SKILLS = _apply_skill_config(SKILL_CONFIG)


def skill_kind(skill: str) -> str:
    return "soft" if skill in SOFT_SKILLS else "hard"


def display_name(skill: str) -> str:
    return DISPLAY_NAMES.get(skill, skill)


CLEARANCE_CONTEXT_RE = re.compile(
    r"(?i)\b(?:clearance|clearances|classified|sci|secret|government|dod|"
    r"security|certification|top)\b"
)

EXCEL_TOKEN_RE = re.compile(r"(?<![\w.])excel(?![\w])", re.IGNORECASE)
EXCEL_VERB_RE = re.compile(r"(?i)^\s+(?:at|in)\b")
EXCEL_CONTEXT_RE = re.compile(
    r"(?i)\b(?:in|with|using|advanced|proficient|expert|skilled|knowledge|skill|"
    r"skills|experience|dashboard|dashboards|spreadsheet|spreadsheets|workbook|"
    r"workbooks|report|reports|model|models|analysis|function|functions|pivot|"
    r"formulas?)[\s,|/:\-]{1,3}$"
)


def _excel_occurrences(text):
    count = 0
    for match in EXCEL_TOKEN_RE.finditer(text):
        after = text[match.end() : match.end() + 8]
        if EXCEL_VERB_RE.match(after):
            continue
        if match.group(0)[0].isupper():
            count += 1
            continue

        before = text[max(0, match.start() - 40) : match.start()]
        if EXCEL_CONTEXT_RE.search(before):
            count += 1
            continue
        if re.search(r"[,|/]\s*$", before) or re.match(r"^\s*[,|/]", after):
            count += 1
    return count


def _term_pattern(term: str):
    term = term.lower()
    spellings = CASE_SENSITIVE_SPELLINGS.get(term)
    if spellings:
        alternation = "|".join(re.escape(spelling) for spelling in spellings)
        return re.compile(rf"(?<![\w.])(?:{alternation})(?![\w/])")
    if len(term) <= 2:
        return re.compile(rf"(?<![\w.]){re.escape(term.upper())}(?![\w/])")
    return re.compile(rf"(?<![\w.]){re.escape(term)}(?![\w])", re.IGNORECASE)


def _count_with_clearance_veto(pattern, text):
    count = 0
    for match in pattern.finditer(text):
        context = text[max(0, match.start() - 40) : match.end() + 40]
        if CLEARANCE_CONTEXT_RE.search(context):
            continue
        count += 1
    return count


def count_term(term: str, text: str) -> int:
    if term == "excel":
        return _excel_occurrences(text)
    pattern = _term_pattern(term)
    if term.lower() == "ts":
        return _count_with_clearance_veto(pattern, text)
    return len(pattern.findall(text))


def term_occurs(term: str, text: str) -> bool:
    return count_term(term, text) > 0


def find_phrase(phrase: str, cleaned_text: str) -> int:
    pattern = rf"(?<![\w.]){re.escape(phrase)}(?![\w])"
    return len(re.findall(pattern, cleaned_text))


def match_skill_in_text(skill: str, text: str):
    count = count_term(skill, text)
    if count:
        return {"skill": skill, "status": "exact", "count": count, "alias": None}

    for alias in SKILL_ALIASES.get(skill, []):
        alias_count = count_term(alias, text)
        if alias_count:
            return {
                "skill": skill,
                "status": "alias",
                "count": alias_count,
                "alias": alias,
            }

    return {"skill": skill, "status": "missing", "count": 0, "alias": None}


STOPWORDS = set(
    "a an the and or but if then else for with without of in on at to from by as "
    "is are was were be been being this that these those you your we our they "
    "their it its will would can could should may might must have has had do does "
    "did not no yes more most other others such than there here about into over "
    "under between across up down out off again further once during before after "
    "above below".split()
)

BOILERPLATE = set(
    "team teams role job work working company candidate candidates experience "
    "year years ability skills skill knowledge strong excellent good great plus "
    "preferred required requirement requirements responsibility responsibilities "
    "looking join help build building including etc new well using use used like "
    "within ensure provide support related field degree based must need needs "
    "development developing environment opportunity opportunities benefits".split()
)

MAX_DYNAMIC_TERMS = 15

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+\-#]*(?:\.[A-Za-z0-9+\-]+)*")
CAPS_TERM_RE = re.compile(
    r"\b[A-Z][A-Za-z0-9+\-#]*(?:\.[A-Za-z0-9+\-]+)*"
    r"(?:\s+[A-Z][A-Za-z0-9+\-#]*(?:\.[A-Za-z0-9+\-]+)*){0,2}\b"
)


def _fixed_terms(existing_skills):
    terms = set(existing_skills)
    for skill in existing_skills:
        terms.update(SKILL_ALIASES.get(skill, []))
    return terms


def _covered_by_fixed(term, fixed_terms):
    padded = f" {term} "
    return any(f" {fixed} " in padded or term == fixed for fixed in fixed_terms)


def _resume_occurrences(term, resume_lowered):
    pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
    count = len(re.findall(pattern, resume_lowered))
    if count:
        return count

    words = term.split()
    last = words[-1]
    if last.endswith("s") and len(last) > 3:
        variant = " ".join(words[:-1] + [last[:-1]])
    else:
        variant = " ".join(words[:-1] + [last + "s"])

    return len(re.findall(rf"(?<!\w){re.escape(variant)}(?!\w)", resume_lowered))


def _contiguous_token_groups(text):
    matches = list(TOKEN_RE.finditer(text))
    if not matches:
        return []

    groups = []
    current = [matches[0]]
    for previous, match in zip(matches, matches[1:]):
        gap = text[previous.end() : match.start()]
        if gap.strip() == "" and "\n" not in gap and "\r" not in gap:
            current.append(match)
        else:
            groups.append(current)
            current = [match]
    groups.append(current)
    return groups


def _is_sentence_start(text, position):
    prefix = text[:position].rstrip()
    return not prefix or prefix[-1] in ".!?\n"


def extract_dynamic_keywords(jd_text, existing_skills, resume_text, max_terms=None):
    if max_terms is None:
        max_terms = MAX_DYNAMIC_TERMS
    token_groups = _contiguous_token_groups(jd_text)
    if not token_groups:
        return []

    counts = Counter()
    for group in token_groups:
        lowered = [match.group(0).lower() for match in group]
        for size in (1, 2, 3):
            for index in range(len(lowered) - size + 1):
                gram = lowered[index : index + size]
                if size == 1 and len(gram[0]) < 3:
                    continue
                if any(t in STOPWORDS or t in BOILERPLATE for t in gram):
                    continue
                counts[" ".join(gram)] += 1

    caps_counts = Counter()
    for match in CAPS_TERM_RE.finditer(jd_text):
        if _is_sentence_start(jd_text, match.start()):
            continue
        lowered_tokens = [token.lower().strip(".") for token in match.group(0).split()]
        if any(t in STOPWORDS or t in BOILERPLATE for t in lowered_tokens):
            continue
        caps_counts[" ".join(lowered_tokens)] += 1

    fixed_terms = _fixed_terms(existing_skills)
    resume_lowered = resume_text.lower()

    ranked = []
    for term, count in counts.items():
        if count < 2:
            continue
        if _covered_by_fixed(term, fixed_terms):
            continue
        ranked.append((term, count, count + 2 * caps_counts.get(term, 0)))

    for term, caps_count in caps_counts.items():
        if counts.get(term, 0) >= 2:
            continue
        if _covered_by_fixed(term, fixed_terms):
            continue
        ranked.append((term, counts.get(term, 0), caps_count * 2))

    ranked.sort(key=lambda item: (-item[2], -len(item[0]), item[0]))

    accepted = []
    accepted_tokens = []
    for term, jd_count, _score in ranked:
        tokens_set = set(term.split())
        if any(
            len(tokens_set & previous) / len(tokens_set) >= 0.5
            for previous in accepted_tokens
        ):
            continue
        accepted.append((term, max(jd_count, 1)))
        accepted_tokens.append(tokens_set)
        if len(accepted) >= max_terms:
            break

    results = []
    for term, jd_count in accepted:
        resume_count = _resume_occurrences(term, resume_lowered)
        results.append(
            {
                "term": term,
                "jd_count": jd_count,
                "resume_count": resume_count,
                "in_resume": resume_count > 0,
            }
        )
    return results


INVENTORY_SPLIT_RE = re.compile(r"\s*[,|;/•·\u2022]\s*")
INVENTORY_BULLET_RE = re.compile(r"^[\s•\-\*\u2022\u25cf\u25cb\u25aa\u25e6>]+")
DENSE_DUMP_MIN_SKILLS = 6
DENSE_DUMP_PROSE_RATIO = 0.25
INVENTORY_TECH_RATIO = 0.75
INVENTORY_MAX_WORDS = 18
INVENTORY_TOKEN_RATIO = 0.25


def _flat_skill_vocab():
    vocab = set()
    for term in list(SKILL_KEYWORDS) + [
        alias for aliases in SKILL_ALIASES.values() for alias in aliases
    ]:
        for part in re.split(r"[^a-z0-9+#.]+", term):
            if len(part) <= 1 or part in STOPWORDS or part in BOILERPLATE:
                continue
            vocab.add(part)
            if part.endswith("s"):
                vocab.add(part[:-1])
    return vocab


_FLAT_VOCAB = None


def _word_in_vocab(word):
    global _FLAT_VOCAB
    if _FLAT_VOCAB is None:
        _FLAT_VOCAB = _flat_skill_vocab()
    for piece in re.split(r"[^a-z0-9+#]+", word.lower()):
        if len(piece) <= 1:
            continue
        if piece in _FLAT_VOCAB:
            return True
        if piece.endswith("s") and piece[:-1] in _FLAT_VOCAB:
            return True
    return False


def is_skill_inventory_line(line):
    stripped = INVENTORY_BULLET_RE.sub("", (line or "").strip()).strip()
    if not stripped:
        return False

    words = re.findall(r"[A-Za-z][A-Za-z0-9+#./\-]*", stripped)
    if len(words) < 2:
        return False

    tech_ratio = sum(1 for word in words if _word_in_vocab(word)) / len(words)
    tokens = [token for token in INVENTORY_SPLIT_RE.split(stripped) if token.strip()]
    if tech_ratio >= INVENTORY_TECH_RATIO and (len(words) >= 5 or len(tokens) >= 2):
        return True

    if len(words) < 5 or len(words) > INVENTORY_MAX_WORDS:
        return False

    if len(tokens) < 4:
        return False

    short_tokens = sum(1 for token in tokens if len(token.split()) <= 4)
    if short_tokens < len(tokens) - 1:
        return False

    return tech_ratio >= INVENTORY_TOKEN_RATIO


def detect_skill_stuffing(resume_text, jd_skills):
    jd_skills = list(jd_skills or [])
    inventory_lines = []
    prose_lines = []
    for line in (resume_text or "").splitlines():
        if is_skill_inventory_line(line):
            inventory_lines.append(line)
        else:
            prose_lines.append(line)

    inventory_text = "\n".join(inventory_lines)
    prose_text = "\n".join(prose_lines)

    inventory_skills = [
        skill for skill in jd_skills if count_term(skill, inventory_text)
    ]
    prose_skills = [skill for skill in jd_skills if count_term(skill, prose_text)]

    distinct = len(inventory_skills)
    required = max(DENSE_DUMP_MIN_SKILLS, math.ceil(0.75 * len(jd_skills)))

    stuffed = (
        len(jd_skills) >= DENSE_DUMP_MIN_SKILLS
        and distinct >= min(required, len(jd_skills))
        and len(prose_skills) <= DENSE_DUMP_PROSE_RATIO * max(distinct, 1)
    )

    return {
        "stuffed": stuffed,
        "inventory_lines": len(inventory_lines),
        "inventory_skills": inventory_skills,
        "prose_skills": prose_skills,
    }
