from app.services.keywords import (
    SKILL_ALIASES,
    SKILL_KEYWORDS,
    SOFT_SKILLS,
    count_term,
    skill_kind,
)

__all__ = [
    "SKILL_ALIASES",
    "SKILL_KEYWORDS",
    "SOFT_SKILLS",
    "extract_skills",
    "skill_kind",
]


def extract_skills(text: str) -> list[str]:
    found = []

    for skill in SKILL_KEYWORDS:
        if count_term(skill, text):
            found.append(skill)
            continue
        aliases = SKILL_ALIASES.get(skill, [])
        if any(count_term(alias, text) for alias in aliases):
            found.append(skill)

    return sorted(set(found))
