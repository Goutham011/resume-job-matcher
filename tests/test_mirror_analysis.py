import numpy as np
import pytest

from app.services.chunking import mirror_analysis
from app.services.matcher import match_resume_to_jd
from tests.fake_model import FakeModel

JD_UNITS = [
    "Build scalable data pipelines with Python.",
    "Design reliable deployment systems for teams.",
    "Write SQL reports for finance leaders.",
    "Monitor production services every single day.",
    "Partner with product managers on roadmaps.",
    "Improve test coverage across backend services.",
]

_BASE = FakeModel()


def _basis(index):
    vector = np.zeros(256, dtype=np.float32)
    vector[index] = 1.0
    return vector


def _near(index, offset):
    vector = np.zeros(256, dtype=np.float32)
    vector[index] = 0.9
    vector[offset] = (1 - 0.9**2) ** 0.5
    return vector


def _make_embed(unit_vectors):
    def fake_embed(model, chunks):
        rows = []
        for chunk in chunks:
            vector = unit_vectors.get(chunk)
            if vector is None:
                vector = _BASE._vector(chunk)
            rows.append(vector)
        matrix = np.asarray(rows, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms

    return fake_embed


def _install(monkeypatch, unit_vectors):
    monkeypatch.setattr("app.services.chunking.embed_chunks", _make_embed(unit_vectors))


def test_verbatim_copy_is_flagged_as_mirrored(monkeypatch):
    unit_vectors = {unit: _basis(index) for index, unit in enumerate(JD_UNITS)}
    _install(monkeypatch, unit_vectors)

    report = mirror_analysis(FakeModel(), "\n".join(JD_UNITS), "\n".join(JD_UNITS))

    assert report["mirrored"] is True
    assert report["paraphrased"] is False
    assert report["verbatim_ratio"] == pytest.approx(1.0)


def test_paraphrased_copy_is_flagged(monkeypatch):
    unit_vectors = {unit: _basis(index) for index, unit in enumerate(JD_UNITS)}
    resume_units = [
        f"Reworded sentence number {index} for my own profile" for index in range(6)
    ]
    for index, unit in enumerate(resume_units):
        unit_vectors[unit] = _near(index, 100 + index)
    _install(monkeypatch, unit_vectors)

    report = mirror_analysis(FakeModel(), "\n".join(resume_units), "\n".join(JD_UNITS))

    assert report["mirrored"] is False
    assert report["paraphrased"] is True
    assert report["copied_ratio"] == pytest.approx(1.0)


def test_edited_paraphrase_is_flagged_at_half_coverage(monkeypatch):
    unit_vectors = {unit: _basis(index) for index, unit in enumerate(JD_UNITS)}
    resume_units = [
        "Reworked deployment routines across several internal teams",
        "Produced reporting datasets used by finance partners",
        "Tracked platform reliability for online commerce systems",
    ]
    for index, unit in enumerate(resume_units):
        unit_vectors[unit] = _near(index, 200 + index)
    _install(monkeypatch, unit_vectors)

    report = mirror_analysis(FakeModel(), "\n".join(resume_units), "\n".join(JD_UNITS))

    assert report["mirrored"] is False
    assert report["copied_ratio"] == pytest.approx(0.5)
    assert report["resume_match_ratio"] == pytest.approx(1.0)
    assert report["paraphrased"] is True


def test_jd_close_below_paraphrase_threshold_is_not_flagged(monkeypatch):
    unit_vectors = {unit: _basis(index) for index, unit in enumerate(JD_UNITS)}
    resume_units = [
        f"Independent statement number {index} about my career" for index in range(6)
    ]
    for index, unit in enumerate(resume_units):
        vector = np.zeros(256, dtype=np.float32)
        vector[index] = 0.87
        vector[80 + index] = (1 - 0.87**2) ** 0.5
        unit_vectors[unit] = vector
    _install(monkeypatch, unit_vectors)

    report = mirror_analysis(FakeModel(), "\n".join(resume_units), "\n".join(JD_UNITS))

    assert report["paraphrased"] is False
    assert report["mirrored"] is False


def test_original_resume_is_not_flagged(monkeypatch):
    unit_vectors = {unit: _basis(index) for index, unit in enumerate(JD_UNITS)}
    resume_units = [
        "Led the migration of billing workloads to managed infrastructure",
        "Reduced onboarding time through workflow automation projects",
        "Owned reliability targets for a high traffic checkout system",
        "Mentored two junior developers through their first releases",
    ]
    for index, unit in enumerate(resume_units):
        unit_vectors[unit] = _basis(20 + index)
    _install(monkeypatch, unit_vectors)

    report = mirror_analysis(FakeModel(), "\n".join(resume_units), "\n".join(JD_UNITS))

    assert report["paraphrased"] is False
    assert report["mirrored"] is False
    assert report["copied_units"] == 0


def test_reassembled_clauses_are_flagged_by_phrase_echoes():
    jd = (
        "We need an analyst to maintain legacy billing ledgers and reconcile "
        "monthly vendor invoices while documenting retention procedures for "
        "compliance teams."
    )
    resume = (
        "I maintain legacy billing ledgers during quarterly audits\n"
        "I reconcile monthly vendor invoices for regional offices\n"
        "I document retention procedures for compliance reviews\n"
    )

    report = mirror_analysis(FakeModel(), resume, jd)

    assert report["echoed_units"] == 3
    assert report["paraphrased"] is True
    assert report["mirrored"] is False


def test_original_wording_has_no_phrase_echoes():
    jd = (
        "We need an analyst to maintain legacy billing ledgers and reconcile "
        "monthly vendor invoices while documenting retention procedures for "
        "compliance teams."
    )
    resume = (
        "Cut reconciliation time in half by automating the weekly close\n"
        "Migrated the finance archive to a searchable document store\n"
        "Trained six new hires on internal audit workflows\n"
    )

    report = mirror_analysis(FakeModel(), resume, jd)

    assert report["echoed_units"] == 0
    assert report["paraphrased"] is False


def test_split_sentences_reassembled_across_lines_are_flagged(monkeypatch):
    unit_vectors = {unit: _basis(index) for index, unit in enumerate(JD_UNITS)}
    first = "Rebuilt internal services for the platform division"
    second = "Handled partner integrations for the commerce group"
    unit_vectors[f"{first} {second}"] = _basis(0)
    third = "Reworded statement one about production work"
    fourth = "Reworded statement two about weekly planning"
    unit_vectors[third] = _near(1, 40)
    unit_vectors[fourth] = _near(2, 41)
    _install(monkeypatch, unit_vectors)

    report = mirror_analysis(
        FakeModel(), "\n".join([first, second, third, fourth]), "\n".join(JD_UNITS)
    )

    assert report["paraphrased"] is True
    assert report["copied_units"] >= 3
    assert report["resume_match_ratio"] >= 0.5


def test_copy_with_filler_still_flagged(monkeypatch):
    unit_vectors = {unit: _basis(index) for index, unit in enumerate(JD_UNITS)}
    units = [
        f"Recycled sentence number {index} outlined for the team" for index in range(4)
    ]
    for index, unit in enumerate(units):
        unit_vectors[unit] = _near(index, 40 + index)
    filler = [
        "Volunteered at the local food bank on weekends",
        "Organized community fundraising events for the chapter",
        "Coached a youth soccer team during the summer",
    ]
    for index, unit in enumerate(filler):
        unit_vectors[unit] = _basis(60 + index)
    _install(monkeypatch, unit_vectors)

    report = mirror_analysis(
        FakeModel(), "\n".join(units + filler), "\n".join(JD_UNITS)
    )

    assert report["paraphrased"] is True


def test_paraphrase_penalty_applies_to_score(monkeypatch):
    unit_vectors = {unit: _basis(index) for index, unit in enumerate(JD_UNITS)}
    resume_units = [
        f"Reworded sentence number {index} for my own profile" for index in range(6)
    ]
    for index, unit in enumerate(resume_units):
        unit_vectors[unit] = _near(index, 100 + index)
    _install(monkeypatch, unit_vectors)

    result = match_resume_to_jd("\n".join(resume_units), "\n".join(JD_UNITS))

    assert result["score_breakdown"]["content_paraphrased"] is True
    assert result["score_breakdown"]["content_mirrored"] is False
    assert result["score_breakdown"]["content_similarity"] < 100.0
    assert any(
        "in different words" in issue["message"] for issue in result["writing_issues"]
    )
    assert any(
        "too closely" in recommendation["title"]
        for recommendation in result["recommendations"]
    )
