from app.services.extractor import extract_skills
from app.services.keywords import (
    detect_skill_stuffing,
    is_skill_inventory_line,
)
from app.services.matcher import match_resume_to_jd

JD_SKILLS = [
    "python",
    "sql",
    "docker",
    "kubernetes",
    "aws",
    "gcp",
    "azure",
    "git",
]

DUMP_LINE = (
    "Skills: Python, SQL, Docker, Kubernetes, AWS, GCP, Azure, Git, Linux, "
    "TensorFlow, PyTorch, PostgreSQL"
)


def test_skill_dump_without_prose_evidence_is_stuffing():
    resume = "Hardworking team player who loves technology.\n" + DUMP_LINE

    report = detect_skill_stuffing(resume, JD_SKILLS)

    assert report["stuffed"] is True
    assert set(report["inventory_skills"]) >= {"python", "sql", "docker"}


def test_prose_evidence_prevents_stuffing_flag():
    resume = (
        "Built Python services and SQL reports for four years.\n"
        "Deployed Docker containers to Kubernetes clusters.\n"
        "Ran workloads on AWS and GCP every week.\n"
        "Automated pipelines with Git and Azure tooling."
    )

    report = detect_skill_stuffing(resume, JD_SKILLS)

    assert report["stuffed"] is False


def test_short_skill_list_is_not_stuffing():
    report = detect_skill_stuffing(
        "Skills: Python, SQL, Docker", ["python", "sql", "docker"]
    )

    assert report["stuffed"] is False


def test_prose_sentence_with_commas_is_not_an_inventory_line():
    line = (
        "Reduced latency by 40%, improved uptime to 99.9%, led a team of five, "
        "and shipped weekly releases to customers."
    )

    assert is_skill_inventory_line(line) is False


BASELINE_LINES = (
    "Built Python services with SQL databases for reporting teams.\n"
    "Shepherded weekly releases for internal customers across regions.\n"
    "Wrote documentation for every deployment and reviewed it monthly.\n"
    "Partnered with support agents to triage incoming defects daily.\n"
    "Automated nightly checks that saved the team ten hours weekly.\n"
    "Presented progress updates to stakeholders during planning cycles.\n"
    "Refactored legacy modules to simplify maintenance for newcomers.\n"
    "Tracked service metrics and raised alerts for unusual patterns.\n"
    "Mentored two junior developers through their first releases.\n"
    "Coordinated with vendors to schedule maintenance windows safely.\n"
)


def test_stuffing_caps_score_gain_versus_baseline():
    jd = (
        "Backend engineer needed with Python, SQL, Docker, Kubernetes, AWS, "
        "GCP, Azure, and Git."
    )
    baseline_resume = BASELINE_LINES
    stuffed_resume = baseline_resume + DUMP_LINE

    baseline = match_resume_to_jd(baseline_resume, jd)
    stuffed = match_resume_to_jd(stuffed_resume, jd)

    assert stuffed["score_breakdown"]["content_stuffing"] is True
    assert baseline["score_breakdown"]["content_stuffing"] is False
    assert stuffed["overall_score"] - baseline["overall_score"] <= 15.0
    assert any(
        "keyword stuffing" in issue["message"] for issue in stuffed["writing_issues"]
    )


def test_stuffing_blends_skill_coverage_with_evidence():
    jd = (
        "Backend engineer needed with Python, SQL, Docker, Kubernetes, AWS, "
        "GCP, Azure, and Git."
    )
    stuffed_resume = BASELINE_LINES + DUMP_LINE

    result = match_resume_to_jd(stuffed_resume, jd)

    coverage = result["score_breakdown"]["skill_coverage"]
    matched = len(result["matched_skills"])
    total = len(result["matched_skills"]) + len(result["missing_skills"])
    assert matched / total == 1.0
    assert 0.0 < coverage < matched / total * 100


def test_config_skill_is_recognized():
    skills = extract_skills("Processed payroll and reconciled accounts payable weekly.")

    assert "payroll" in skills
    assert "accounts payable" in skills
