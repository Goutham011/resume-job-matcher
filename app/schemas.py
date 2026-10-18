from pydantic import BaseModel, Field, field_validator

MIN_TEXT_CHARS = 20
MAX_RESUME_CHARS = 200_000
MAX_JD_CHARS = 50_000


class MatchRequest(BaseModel):
    resume_text: str = Field(..., min_length=1, max_length=MAX_RESUME_CHARS)
    job_description: str = Field(..., min_length=1, max_length=MAX_JD_CHARS)

    @field_validator("resume_text", "job_description")
    @classmethod
    def _require_actual_text(cls, value):
        stripped = value.strip()
        if len(stripped) < MIN_TEXT_CHARS:
            raise ValueError(
                f"needs at least {MIN_TEXT_CHARS} characters of actual text"
            )
        return stripped


class ScoreBreakdown(BaseModel):
    content_similarity: float
    skill_coverage: float | None = None
    content_weight: int
    skill_weight: int
    resume_chunks: int = 0
    jd_chunks: int = 0
    chunk_max_tokens: int = 256
    content_mirrored: bool = False
    content_paraphrased: bool = False
    content_stuffing: bool = False


class WritingIssue(BaseModel):
    category: str
    message: str
    suggestion: str | None = None
    snippet: str | None = None


class Recommendation(BaseModel):
    priority: str
    title: str
    detail: str


class AtsIssue(BaseModel):
    severity: str
    message: str
    suggestion: str


class AtsAudit(BaseModel):
    parseability_score: int
    issues: list[AtsIssue]
    checks_passed: list[str]


class RequirementAnalysis(BaseModel):
    must_have: list[str]
    preferred: list[str]


class KnockoutCheck(BaseModel):
    topic: str
    jd_says: str
    resume_says: str
    status: str
    advice: str


class KeywordCoverage(BaseModel):
    skill: str
    status: str
    count: int
    alias: str | None = None
    kind: str | None = None


class DynamicKeyword(BaseModel):
    term: str
    jd_count: int
    resume_count: int
    in_resume: bool


class RequirementMatch(BaseModel):
    requirement: str
    kind: str
    status: str
    similarity: float
    best_match: str | None = None


class MatchResponse(BaseModel):
    overall_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    resume_keywords: list[str]
    jd_keywords: list[str]
    explanation: str
    score_breakdown: ScoreBreakdown
    skill_mentions: dict[str, int]
    writing_issues: list[WritingIssue]
    recommendations: list[Recommendation]
    keyword_coverage: list[KeywordCoverage]
    dynamic_keywords: list[DynamicKeyword]
    requirements: RequirementAnalysis
    knockout_checks: list[KnockoutCheck]
    requirement_matches: list[RequirementMatch]
    ats_audit: AtsAudit | None = None
