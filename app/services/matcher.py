from sentence_transformers import SentenceTransformer, util

from app.services.extractor import extract_skills

_model = None


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model


def build_explanation(matched_skills, missing_skills, score):
    if score >= 75:
        strength = "strong"
    elif score >= 40:
        strength = "moderate"
    else:
        strength = "weak"

    matched_text = ", ".join(matched_skills[:5]) if matched_skills else "none"
    missing_text = ", ".join(missing_skills[:5]) if missing_skills else "none"

    return (
        f"This is a {strength} match. "
        f"Matched skills: {matched_text}. "
        f"Missing skills: {missing_text}."
    )


def match_resume_to_jd(resume_text: str, jd_text: str) -> dict:
    resume_skills = extract_skills(resume_text)
    jd_skills = extract_skills(jd_text)

    matched_skills = sorted(set(resume_skills) & set(jd_skills))
    missing_skills = sorted(set(jd_skills) - set(resume_skills))

    model = get_model()

    resume_embedding = model.encode(resume_text, convert_to_tensor=True)
    jd_embedding = model.encode(jd_text, convert_to_tensor=True)

    semantic_similarity = (
        float(util.cos_sim(resume_embedding, jd_embedding).item()) * 100
    )

    if jd_skills:
        skill_overlap = (len(matched_skills) / len(jd_skills)) * 100
    else:
        skill_overlap = 0

    overall_score = round((0.65 * semantic_similarity) + (0.35 * skill_overlap), 2)

    explanation = build_explanation(matched_skills, missing_skills, overall_score)

    return {
        "overall_score": overall_score,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "resume_keywords": resume_skills,
        "jd_keywords": jd_skills,
        "explanation": explanation,
    }
