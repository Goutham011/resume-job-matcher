from pydantic import BaseModel, Field


class MatchRequest(BaseModel):
    resume_text: str = Field(..., min_length=20)
    job_description: str = Field(..., min_length=20)


class MatchResponse(BaseModel):
    overall_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    resume_keywords: list[str]
    jd_keywords: list[str]
    explanation: str
