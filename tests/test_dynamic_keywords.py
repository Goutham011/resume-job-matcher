from app.services.keywords import extract_dynamic_keywords


def test_picks_up_terms_missing_from_fixed_skills():
    jd = (
        "We use Salesforce and HubSpot daily. "
        "Salesforce administration is central to this role."
    )
    resume = "Worked with Salesforce for two years."

    keywords = extract_dynamic_keywords(jd, ["python"], resume)

    terms = [item["term"] for item in keywords]
    assert "salesforce" in terms

    salesforce = next(item for item in keywords if item["term"] == "salesforce")
    assert salesforce["in_resume"] is True
    assert salesforce["resume_count"] >= 1


def test_marks_terms_not_in_resume():
    jd = "We need deep Terraform experience. Terraform modules everywhere."
    resume = "Built services with Python and Docker."

    keywords = extract_dynamic_keywords(jd, ["python"], resume)

    terraform = next(item for item in keywords if item["term"] == "terraform")
    assert terraform["in_resume"] is False
    assert terraform["resume_count"] == 0


def test_excludes_fixed_skills_and_aliases():
    jd = "Kubernetes kubernetes kubernetes and Python python python."

    keywords = extract_dynamic_keywords(jd, ["kubernetes", "python"], "resume text")

    terms = [item["term"] for item in keywords]
    assert "kubernetes" not in terms
    assert "python" not in terms
    assert terms == []


def test_excludes_stopwords_and_boilerplate():
    jd = (
        "The team values your experience with the company. "
        "You will work with the team on the job every year."
    )

    keywords = extract_dynamic_keywords(jd, [], "resume text")

    terms = [item["term"] for item in keywords]
    assert "the team" not in terms
    assert "experience" not in terms


def test_respects_max_terms():
    jd = " ".join(
        f"Term{i} appears repeatedly. Term{i} is important." for i in range(30)
    )

    keywords = extract_dynamic_keywords(jd, [], "resume text", max_terms=5)

    assert len(keywords) <= 5


def test_proper_nouns_picked_up_even_once():
    jd = "Experience with GraphQL is a plus. We build APIs."

    keywords = extract_dynamic_keywords(jd, [], "resume text")

    terms = [item["term"] for item in keywords]
    assert "graphql" in terms


def test_empty_jd_returns_empty_list():
    assert extract_dynamic_keywords("", [], "resume text") == []


def test_no_phantom_ngrams_across_commas():
    jd = "Flask, Django, Web. Flask, Django, Web."

    keywords = extract_dynamic_keywords(jd, [], "resume text")

    terms = [item["term"] for item in keywords]
    assert "flask django" not in terms
    assert "django web" not in terms


def test_contiguous_phrases_are_kept():
    jd = "Customer discovery drives our roadmap. Customer discovery is key."

    keywords = extract_dynamic_keywords(jd, [], "resume text")

    terms = [item["term"] for item in keywords]
    assert "customer discovery" in terms
