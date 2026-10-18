from app.services.extractor import extract_skills, skill_kind


def test_extract_skills_finds_expected_keywords():
    text = """
    Experienced Python developer with FastAPI, SQL, Docker, GitHub,
    and AWS experience. Built REST API services.
    """

    skills = extract_skills(text)

    assert "python" in skills
    assert "fastapi" in skills
    assert "sql" in skills
    assert "docker" in skills
    assert "aws" in skills
    assert "github" in skills
    assert "rest api" in skills


def test_extract_skills_understands_aliases():
    skills = extract_skills("Deployed workloads on k8s and wrote ML pipelines.")

    assert "kubernetes" in skills
    assert "machine learning" in skills


def test_extract_skills_does_not_match_substrings():
    skills = extract_skills("Digital marketing specialist with a blog about SQLite")

    assert "git" not in skills
    assert "sql" not in skills


def test_extract_skills_finds_marketing_and_community_skills():
    text = (
        "Marketing Intern experienced in publicity campaigns, event planning, "
        "community engagement, audience outreach, and market research. "
        "Skilled in Excel, Power BI, SEO, and social media."
    )

    skills = extract_skills(text)

    for expected in [
        "marketing",
        "publicity",
        "event planning",
        "community engagement",
        "audience outreach",
        "market research",
        "excel",
        "power bi",
        "seo",
        "social media",
    ]:
        assert expected in skills


def test_extract_skills_understands_business_aliases():
    skills = extract_skills(
        "Ran search engine optimization and built PowerBI dashboards. "
        "Handled customer relationship management daily."
    )

    assert "seo" in skills
    assert "power bi" in skills
    assert "crm" in skills


def test_extract_soft_skills_and_kinds():
    skills = extract_skills("Strong communication and teamwork skills.")

    assert "communication" in skills
    assert "teamwork" in skills
    assert skill_kind("communication") == "soft"
    assert skill_kind("python") == "hard"


def test_excel_verb_is_not_a_skill():
    skills = extract_skills("I excel at communication and teamwork.")

    assert "excel" not in skills


def test_capitalized_excel_is_a_skill():
    skills = extract_skills("Built reporting workbooks in Advanced Excel.")

    assert "excel" in skills


def test_ambiguous_short_aliases_need_contextual_spelling():
    assert "sem" in extract_skills("Ran Google Ads and SEM campaigns.")
    assert "sem" not in extract_skills("Compared sem results quickly.")

    assert "machine learning" in extract_skills("Built ML pipelines.")
    assert "machine learning" not in extract_skills("We used 5 ml of reagent.")


def test_pr_is_not_matched_as_public_relations():
    assert "public relations" not in extract_skills("Ran PR campaigns for the club.")
    assert "public relations" in extract_skills(
        "Handled public relations for the club."
    )


def test_lowercase_excel_needs_tech_context():
    assert "excel" not in extract_skills("I excel daily in everything I try.")
    assert "excel" not in extract_skills("I used excel daily for tracking.")
    assert "excel" in extract_skills("Skilled in excel, python and sql.")
    assert "excel" in extract_skills("Built dashboards in excel for the team.")


def test_ts_clearance_is_not_typescript():
    skills = extract_skills("Active TS/SCI clearance with government experience.")

    assert "typescript" not in skills


def test_ts_still_matches_typescript_in_code_context():
    skills = extract_skills("Built TS services and refactored TS modules weekly.")

    assert "typescript" in skills
