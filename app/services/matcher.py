import re

import numpy as np

from app.services.chunking import (
    max_tokens_for,
    mean_pooled_similarity,
    mirror_analysis,
)
from app.services.extractor import extract_skills, skill_kind
from app.services.keywords import (
    detect_skill_stuffing,
    extract_dynamic_keywords,
    match_skill_in_text,
)
from app.services.model_manager import model_manager
from app.services.requirements import (
    check_knockouts,
    estimate_experience_years,
    extract_requirements,
)
from app.services.reviewer import (
    analyze_resume,
    build_recommendations,
    count_skill_mentions,
)

CONTENT_WEIGHT = 65
SKILL_WEIGHT = 35

REQUIREMENT_COVERED = 50.0
REQUIREMENT_PARTIAL = 30.0
MAX_REQUIREMENTS = 18
MAX_CHUNKS = 120

MIRROR_PENALTY = 0.8
PARAPHRASE_PENALTY = 0.9
STUFFING_PENALTY = 0.85
STUFFING_EVIDENCE_WEIGHT = 0.75
MIRROR_MESSAGE = (
    "Large parts of your resume match the posting word-for-word. Recruiters "
    "and ATS tools can flag this as copied content."
)
MIRROR_SUGGESTION = (
    "Rewrite bullets in your own words and lead with your own achievements "
    "instead of the posting's phrasing."
)
PARAPHRASE_MESSAGE = (
    "Large parts of your resume closely track the posting's wording and "
    "structure in different words. Recruiters may treat this as copied content."
)
PARAPHRASE_SUGGESTION = (
    "Rework these sections around your own projects and results rather than "
    "restating the posting sentence by sentence."
)
STUFFING_MESSAGE = (
    "Your resume lists many of the posting's skills in one block without "
    "showing where you used them. Recruiters and ATS keyword checks treat "
    "unexplained skill lists as keyword stuffing."
)
STUFFING_SUGGESTION = (
    "Keep the skills list short and back each important skill with a concrete "
    "example from your experience."
)

BOILERPLATE_SKIP = [
    "we offer",
    "equal opportunity",
    "about us",
    "our company",
    "benefits include",
    "apply now",
    "join our",
]


def get_model():
    return model_manager.get_model()


def build_explanation(matched_skills, missing_skills, score):
    if score >= 75:
        strength = "strong"
    elif score >= 40:
        strength = "moderate"
    else:
        strength = "weak"

    if not matched_skills and not missing_skills:
        return (
            f"This is a {strength} match based on overall wording. "
            "The posting doesn't name specific skills that could be checked."
        )

    matched_text = ", ".join(matched_skills[:5]) if matched_skills else "none"
    missing_text = ", ".join(missing_skills[:5]) if missing_skills else "none"

    return (
        f"This is a {strength} match. "
        f"Matched skills: {matched_text}. "
        f"Missing skills: {missing_text}."
    )


def _resume_chunks(resume_text):
    chunks = []
    for line in resume_text.splitlines():
        line = re.sub(r"^[\s•\-\*\u2022\u25cf\u25cb\u25aa\u25e6]+", "", line.strip())
        if not line or len(line.split()) < 4:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            sentence = sentence.strip()
            if len(sentence.split()) >= 4:
                chunks.append(sentence)
    return chunks[:MAX_CHUNKS]


def _requirement_sentences(jd_text, requirements):
    ordered = [(text, "required") for text in requirements["must_have"]]
    ordered += [(text, "preferred") for text in requirements["preferred"]]
    seen = {text.lower() for text, _ in ordered}

    for sentence in re.split(r"(?<=[.!?])\s+|\n+", jd_text):
        sentence = re.sub(r"^[\s•\-\*\u2022>]+", "", sentence).strip()
        lowered = sentence.lower()
        if not sentence or lowered in seen:
            continue
        if not 4 <= len(sentence.split()) <= 45:
            continue
        if any(skip in lowered for skip in BOILERPLATE_SKIP):
            continue
        seen.add(lowered)
        ordered.append((sentence, "general"))
        if len(ordered) >= MAX_REQUIREMENTS:
            break

    return ordered[:MAX_REQUIREMENTS]


def _weighted_skill_coverage(covered_skills, jd_skills):
    covered = set(covered_skills)
    total = 0.0
    hits = 0.0
    for skill in jd_skills:
        weight = 0.5 if skill_kind(skill) == "soft" else 1.0
        total += weight
        if skill in covered:
            hits += weight
    if total <= 0:
        return None
    return (hits / total) * 100


def _encode_matrix(model, texts):
    embeddings = model.encode(texts, normalize_embeddings=True)
    matrix = np.asarray(embeddings, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    return matrix


def match_requirement_coverage(resume_text, jd_text, requirements, model=None):
    model = model or get_model()
    requirement_items = _requirement_sentences(jd_text, requirements)
    chunks = _resume_chunks(resume_text)

    if not requirement_items or not chunks:
        return []

    requirement_embeddings = _encode_matrix(
        model, [text for text, _ in requirement_items]
    )
    chunk_embeddings = _encode_matrix(model, chunks)
    similarities = requirement_embeddings @ chunk_embeddings.T

    results = []
    for (text, kind), row in zip(requirement_items, similarities):
        best_index = int(np.argmax(row))
        best_similarity = max(0.0, min(100.0, float(row[best_index]) * 100))

        if best_similarity >= REQUIREMENT_COVERED:
            status = "covered"
        elif best_similarity >= REQUIREMENT_PARTIAL:
            status = "partial"
        else:
            status = "missing"

        results.append(
            {
                "requirement": text,
                "kind": kind,
                "status": status,
                "similarity": round(best_similarity, 1),
                "best_match": chunks[best_index] if status != "missing" else None,
            }
        )

    return results


def match_resume_to_jd(resume_text: str, jd_text: str) -> dict:
    resume_skills = extract_skills(resume_text)
    jd_skills = extract_skills(jd_text)

    matched_skills = sorted(set(resume_skills) & set(jd_skills))
    missing_skills = sorted(set(jd_skills) - set(resume_skills))

    model = get_model()

    similarity, resume_chunk_count, jd_chunk_count = mean_pooled_similarity(
        model, resume_text, jd_text
    )
    semantic_similarity = max(0.0, min(100.0, similarity * 100))

    mirror = mirror_analysis(model, resume_text, jd_text)
    mirrored = mirror["mirrored"]
    paraphrased = mirror["paraphrased"]
    stuffing = detect_skill_stuffing(resume_text, jd_skills)

    if mirrored:
        semantic_similarity = round(semantic_similarity * MIRROR_PENALTY, 2)
    elif paraphrased:
        semantic_similarity = round(semantic_similarity * PARAPHRASE_PENALTY, 2)

    if stuffing["stuffed"]:
        semantic_similarity = round(semantic_similarity * STUFFING_PENALTY, 2)

    if jd_skills:
        skill_overlap = _weighted_skill_coverage(matched_skills, jd_skills)
        if stuffing["stuffed"]:
            evidenced = [
                skill for skill in matched_skills if skill in stuffing["prose_skills"]
            ]
            evidenced_coverage = _weighted_skill_coverage(evidenced, jd_skills) or 0.0
            skill_overlap = (
                1 - STUFFING_EVIDENCE_WEIGHT
            ) * skill_overlap + STUFFING_EVIDENCE_WEIGHT * evidenced_coverage
        content_weight = CONTENT_WEIGHT
        skill_weight = SKILL_WEIGHT
    else:
        skill_overlap = None
        content_weight = 100
        skill_weight = 0

    overall_score = (content_weight / 100) * semantic_similarity + (
        skill_weight / 100
    ) * (skill_overlap or 0.0)
    overall_score = round(max(0.0, min(100.0, overall_score)), 2)

    score_breakdown = {
        "content_similarity": round(semantic_similarity, 2),
        "skill_coverage": (
            round(skill_overlap, 2) if skill_overlap is not None else None
        ),
        "content_weight": content_weight,
        "skill_weight": skill_weight,
        "resume_chunks": resume_chunk_count,
        "jd_chunks": jd_chunk_count,
        "chunk_max_tokens": max_tokens_for(model),
        "content_mirrored": mirrored,
        "content_paraphrased": paraphrased,
        "content_stuffing": stuffing["stuffed"],
    }

    writing_issues = analyze_resume(resume_text, jd_text=jd_text, jd_skills=jd_skills)
    if mirrored:
        writing_issues.append(
            {
                "category": "style",
                "message": MIRROR_MESSAGE,
                "suggestion": MIRROR_SUGGESTION,
                "snippet": None,
            }
        )
    elif paraphrased:
        writing_issues.append(
            {
                "category": "style",
                "message": PARAPHRASE_MESSAGE,
                "suggestion": PARAPHRASE_SUGGESTION,
                "snippet": None,
            }
        )
    if stuffing["stuffed"]:
        writing_issues.append(
            {
                "category": "content",
                "message": STUFFING_MESSAGE,
                "suggestion": STUFFING_SUGGESTION,
                "snippet": None,
            }
        )
    skill_mentions = count_skill_mentions(jd_text, jd_skills)
    keyword_coverage = [
        {**match_skill_in_text(skill, resume_text), "kind": skill_kind(skill)}
        for skill in jd_skills
    ]
    requirements = extract_requirements(jd_text)
    years_estimate = estimate_experience_years(resume_text)
    knockout_checks = check_knockouts(jd_text, resume_text, years_estimate)
    requirement_matches = match_requirement_coverage(
        resume_text, jd_text, requirements, model
    )
    dynamic_keywords = extract_dynamic_keywords(jd_text, jd_skills, resume_text)

    recommendations = build_recommendations(
        resume_text=resume_text,
        jd_text=jd_text,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        breakdown=score_breakdown,
        skill_mentions=skill_mentions,
        issues=writing_issues,
        mirrored=mirrored,
        paraphrased=paraphrased,
    )

    explanation = build_explanation(matched_skills, missing_skills, overall_score)

    return {
        "overall_score": overall_score,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "resume_keywords": resume_skills,
        "jd_keywords": jd_skills,
        "explanation": explanation,
        "score_breakdown": score_breakdown,
        "skill_mentions": skill_mentions,
        "writing_issues": writing_issues,
        "recommendations": recommendations,
        "keyword_coverage": keyword_coverage,
        "requirements": requirements,
        "knockout_checks": knockout_checks,
        "requirement_matches": requirement_matches,
        "dynamic_keywords": dynamic_keywords,
    }
