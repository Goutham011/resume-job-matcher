from app.services.headings import match_headings
from app.services.reviewer import analyze_resume


def test_combined_headings_are_recognized():
    assert match_headings("Experience & Education") == ["Experience", "Education"]
    assert match_headings("Skills/Technologies") == ["Skills"]
    assert match_headings("Work History/Academic Background/Core Competencies") == [
        "Experience",
        "Education",
        "Skills",
    ]
    assert match_headings("Education, Awards & Certifications") == [
        "Education",
        "Awards",
        "Certifications",
    ]


def test_combined_headings_do_not_trigger_on_prose():
    assert match_headings("Python, AWS and Docker") == []
    assert match_headings("Skills and experience in marketing") == []
    assert match_headings("R&D Operations") == []


def test_variant_headings_are_not_flagged_as_missing_sections():
    resume = (
        "Jordan Lee\n"
        "jordan.lee@example.com | +1 555 123 4567 | linkedin.com/in/jordan\n"
        "Work History\n"
        "Software Engineer, Acme Corp\n"
        "Jan 2020 - Present\n"
        "Built backend APIs in Python for billing teams.\n"
        "Academic Background\n"
        "BSc Computer Science, 2020\n"
        "Core Competencies\n"
        "Python, SQL, Docker\n"
    )

    issues = analyze_resume(resume)
    messages = " ".join(issue["message"] for issue in issues)

    assert "No 'Experience' section" not in messages
    assert "No 'Education' section" not in messages
    assert "No 'Skills' section" not in messages


def test_reviewer_flags_linkedin_only_when_link_present():
    resume = (
        "Jordan Lee\n"
        "jordan.lee@example.com | +1 555 123 4567\n"
        "Experience\n"
        "Built backend APIs in Python for billing teams every single day.\n"
        "Education\n"
        "BSc Computer Science, 2020\n"
        "Skills\n"
        "Python, SQL, Docker\n"
        "I heard about this on LinkedIn once.\n"
    )

    issues = analyze_resume(resume)

    assert any("LinkedIn" in issue["message"] for issue in issues)
