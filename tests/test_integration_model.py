import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MODEL_TESTS") != "1",
    reason="set RUN_MODEL_TESTS=1 to run tests against the real embedding model",
)


def test_real_model_scores_related_text_above_unrelated():
    from app.services.matcher import match_resume_to_jd

    resume = (
        "Backend engineer with Python, FastAPI, SQL, and Docker experience "
        "building REST APIs for payments."
    )
    good_jd = (
        "Looking for a backend engineer with Python, FastAPI, SQL, and "
        "Docker to build payment APIs."
    )
    bad_jd = (
        "Seeking a pastry chef with cake decorating and inventory skills "
        "for a busy bakery kitchen."
    )

    good = match_resume_to_jd(resume, good_jd)["overall_score"]
    bad = match_resume_to_jd(resume, bad_jd)["overall_score"]

    assert good > bad
    assert good > 50
