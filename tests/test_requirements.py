from app.services.requirements import (
    check_knockouts,
    estimate_experience_years,
    extract_requirements,
)


def test_extract_requirements_splits_must_and_preferred():
    jd = (
        "5+ years of backend experience required. "
        "Bachelor's degree required. "
        "Experience with Kubernetes is preferred. "
        "Familiarity with AWS is a plus."
    )
    result = extract_requirements(jd)

    assert any("5+ years" in item for item in result["must_have"])
    assert any("degree" in item for item in result["must_have"])
    assert any("Kubernetes" in item for item in result["preferred"])
    assert any("AWS" in item for item in result["preferred"])


def test_estimate_experience_years_from_date_ranges():
    resume = (
        "Software Engineer, Acme Corp\n"
        "Mar 2019 - Present\n"
        "Built backend systems for the billing team.\n"
    )
    result = estimate_experience_years(resume)

    assert result["years"] is not None
    assert result["years"] >= 5
    assert result["source"] == "date ranges"


def test_estimate_experience_years_from_statement():
    resume = "Engineer with 6 years of experience in backend development."
    result = estimate_experience_years(resume)

    assert result["years"] == 6.0
    assert result["source"] == "experience statement"


def test_check_knockouts_flags_years_gap():
    jd = (
        "Senior engineer needed. Must have 10+ years of backend experience. "
        "Bachelor's degree required."
    )
    resume = (
        "Software Engineer\n"
        "Jan 2020 - Jan 2023\n"
        "Built APIs in Python.\n"
        "Bachelor of Science in Computer Science"
    )
    years = estimate_experience_years(resume)
    checks = check_knockouts(jd, resume, years)

    years_check = next(c for c in checks if c["topic"] == "Years of experience")
    assert years_check["status"] == "possible_gap"

    degree_check = next(c for c in checks if c["topic"] == "Degree")
    assert degree_check["status"] == "match"


def test_check_knockouts_us_authorization_info():
    jd = "Candidates must be authorized to work in the US. No sponsorship."
    checks = check_knockouts(jd, "Python developer.", {"years": None, "source": "none"})

    auth = next(c for c in checks if c["topic"] == "Work authorization")
    assert auth["status"] == "info"


def test_estimate_experience_accepts_double_hyphen_ranges():
    resume = "Engineer, Acme Corp\nJan 2024 -- Present\nBuilt backend APIs daily."

    result = estimate_experience_years(resume)

    assert result["years"] is not None
    assert result["years"] >= 1.5
    assert result["source"] == "date ranges"


def test_education_dates_are_not_counted_as_experience():
    resume = (
        "Experience\n"
        "Software Engineer, Acme Corp\n"
        "Jan 2020 - Jan 2022\n"
        "Built backend APIs in Python.\n"
        "Education\n"
        "Bachelor of Technology\n"
        "2016 - 2020\n"
    )

    result = estimate_experience_years(resume)

    assert result["years"] is not None
    assert result["years"] < 3


def test_years_in_business_is_not_a_years_requirement():
    jd = "We have 10 years in business and a fast-growing team."

    checks = check_knockouts(
        jd, "Python developer.", {"years": 1.0, "source": "date ranges"}
    )

    assert not any(check["topic"] == "Years of experience" for check in checks)


def test_years_requirement_requires_experience_context():
    jd = "Must have 5+ years of experience in backend development."

    checks = check_knockouts(
        jd, "Python developer.", {"years": 1.0, "source": "date ranges"}
    )

    years_check = next(c for c in checks if c["topic"] == "Years of experience")
    assert years_check["status"] == "possible_gap"


def test_at_least_n_years_is_detected():
    from app.services.requirements import find_years_requirement

    assert find_years_requirement("Minimum of 8 years in a similar role.") == 8
    assert find_years_requirement("At least 4 years supporting customers.") == 4


def test_years_range_uses_lower_bound():
    from app.services.requirements import find_years_requirement

    assert find_years_requirement("3-5 years of experience in analytics.") == 3
    assert find_years_requirement("5 to 7 years of experience required.") == 5


def test_years_mention_inside_education_is_ignored():
    resume = (
        "Experience\n"
        "Software Engineer, Acme Corp\n"
        "Jan 2024 - Jan 2025\n"
        "Built backend APIs in Python.\n"
        "Education\n"
        "Bachelor of Technology\n"
        "4 years of coursework, 2016 - 2020\n"
    )

    result = estimate_experience_years(resume)

    assert result["years"] is not None
    assert result["years"] < 3
