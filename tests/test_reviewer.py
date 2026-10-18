from app.services.reviewer import (
    _logical_lines,
    analyze_resume,
    build_recommendations,
    count_skill_mentions,
)


def test_analyze_resume_flags_spelling_and_grammar():
    text = "I recieve the the reports and worked on a engineer's dashboard."
    issues = analyze_resume(text)

    categories = {issue["category"] for issue in issues}
    assert "spelling" in categories
    assert "grammar" in categories
    assert any("recieve" in issue["message"].lower() for issue in issues)


def test_analyze_resume_flags_structure_problems():
    issues = analyze_resume("python developer with docker experience")
    messages = [issue["message"] for issue in issues]

    assert any("short" in message for message in messages)
    assert any("email" in message for message in messages)
    assert any("Skills" in message for message in messages)


def test_analyze_resume_clean_text_has_no_major_issues():
    text = (
        "Goutham Sai\n"
        "goutham@example.com | +91 9876543210 | linkedin.com/in/goutham\n"
        "Experience\n"
        "Built REST API services in Python and FastAPI that reduced latency "
        "by 40% and served 10k users.\n"
        "Led a team of 3 engineers to ship a Docker-based deployment pipeline "
        "across 12 releases.\n"
        "Designed PostgreSQL schemas for a billing platform that processed "
        "1,200 invoices per day.\n"
        "Automated nightly data checks with Python scripts, saving the team "
        "10 hours every week.\n"
        "Mentored 2 junior developers and reviewed more than 300 pull "
        "requests on GitHub.\n"
        "Cut cloud costs by 25% by right-sizing AWS instances across "
        "3 environments.\n"
        "Collaborated with product managers to clarify requirements and "
        "estimate delivery dates for each sprint.\n"
        "Presented weekly progress reports to stakeholders and tracked "
        "risks in Jira.\n"
        "Wrote technical guides that new hires used during their first week.\n"
        "Skills\n"
        "Python, FastAPI, SQL, Docker, AWS, Kubernetes, Git, Linux, and "
        "REST API design.\n"
        "Education\n"
        "Bachelor of Technology in Computer Science, 2022.\n"
        "Certifications\n"
        "AWS Certified Cloud Practitioner, 2023."
    )
    issues = analyze_resume(text)

    assert not [issue for issue in issues if issue["category"] == "spelling"]
    assert not [issue for issue in issues if issue["category"] == "structure"]


def test_recommendations_prioritize_missing_skills():
    recs = build_recommendations(
        resume_text="Python developer with FastAPI and SQL.",
        jd_text=(
            "Backend engineer needed with Python, SQL, and Kubernetes. "
            "Kubernetes experience required."
        ),
        matched_skills=["python", "sql"],
        missing_skills=["kubernetes"],
        breakdown={
            "content_similarity": 60.0,
            "skill_coverage": 66.67,
            "content_weight": 65,
            "skill_weight": 35,
        },
        skill_mentions={"python": 1, "sql": 1, "kubernetes": 2},
        issues=[],
    )

    assert recs[0]["priority"] == "high"
    assert "kubernetes" in recs[0]["detail"]
    assert any(rec["title"].startswith("Use the posting's vocabulary") for rec in recs)


def test_build_recommendations_handles_no_issues():
    recs = build_recommendations(
        resume_text="Python developer. " * 40,
        jd_text="Python developer needed.",
        matched_skills=["python"],
        missing_skills=[],
        breakdown={
            "content_similarity": 85.0,
            "skill_coverage": 100.0,
            "content_weight": 65,
            "skill_weight": 35,
        },
        skill_mentions={"python": 1},
        issues=[],
    )

    assert recs
    assert all(rec["priority"] in {"high", "medium", "low"} for rec in recs)


def test_count_skill_mentions():
    text = "Python, python everywhere. Kubernetes once."
    counts = count_skill_mentions(text, ["python", "kubernetes", "docker"])

    assert counts["python"] == 2
    assert counts["kubernetes"] == 1
    assert counts["docker"] == 0


def test_wrapped_lines_do_not_trigger_lowercase_flag():
    text = (
        "Goutham Sai\n"
        "goutham@example.com | +91 9876543210 | linkedin.com/in/goutham\n"
        "Professional Summary\n"
        "Led a 10-member publicity team for a CSE symposium. Contributed\n"
        "to a campaign associated with a 40% increase in participation\n"
        "at an event attended by more than 2,000 people.\n"
        "Helped coordinate more than 15\n"
        "campus events annually.\n"
        "Interested in AI product marketing, market and competitive\n"
        "research, campaign execution, content strategy, developer\n"
        "communities, partnerships, and growth initiatives.\n"
    )
    issues = analyze_resume(text)

    assert not [issue for issue in issues if "lowercase" in issue["message"].lower()]


def test_unwrapped_bullets_with_mixed_endings_are_not_flagged():
    text = (
        "Experience\n"
        "- Led a 10-member publicity team for a CSE symposium\n"
        "coordinating campaign execution and audience outreach\n"
        "- Contributed to publicity initiatives for an event\n"
        "attended by more than 2,000 people\n"
        "- Coordinated event planning and stakeholder communication\n"
        "while helping execute campus events\n"
        "- Supported team coordination and logistics across activities\n"
    )
    issues = analyze_resume(text)

    assert not [
        issue for issue in issues if "mix ending punctuation" in issue["message"]
    ]


def test_marked_bullets_with_mixed_endings_are_flagged():
    text = (
        "- Built REST APIs in Python for the payments team\n"
        "- Led migration of 12 services to Docker containers\n"
        "- Automated nightly data checks across all pipelines.\n"
        "- Mentored two junior developers on code reviews\n"
        "- Cut cloud costs by 25% across environments.\n"
        "- Presented weekly progress reports to stakeholders\n"
    )
    issues = analyze_resume(text)

    assert [issue for issue in issues if "mix ending punctuation" in issue["message"]]


def test_analyze_resume_flags_keyword_stuffing():
    resume = ("Python " * 40) + "\nBuilt dashboards and reports for the team."
    jd = "Looking for a Python developer to build dashboards."

    issues = analyze_resume(resume, jd_text=jd, jd_skills=["python"])

    assert [issue for issue in issues if "appears about" in issue["message"]]


def test_keyword_stuffing_is_conservative_under_threshold():
    resume = ("Python " * 11) + "\nBuilt dashboards and reports for the team."
    jd = "Looking for a Python developer to build dashboards."

    issues = analyze_resume(resume, jd_text=jd, jd_skills=["python"])

    assert not [issue for issue in issues if "appears about" in issue["message"]]


def test_contact_lines_are_not_merged_into_previous_line():
    text = (
        "Built REST APIs in Python for the payments team\n"
        "goutham@example.com | +1 555 123 4567\n"
        "linkedin.com/in/goutham\n"
    )

    assert _logical_lines(text) == [
        "Built REST APIs in Python for the payments team",
        "goutham@example.com | +1 555 123 4567",
        "linkedin.com/in/goutham",
    ]


def test_url_lines_do_not_trigger_lowercase_flags():
    text = (
        "Experience\n"
        "Built REST APIs in Python for the payments team.\n"
        "https://github.com/goutham\n"
        "www.goutham.dev\n"
    )

    issues = analyze_resume(text)

    assert not [issue for issue in issues if "lowercase" in issue["message"].lower()]
