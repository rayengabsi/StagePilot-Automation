from __future__ import annotations

from app.config.settings import FilterRules
from app.db.models.jobs import Job
from app.domain.matching.entities import RejectionReason
from app.domain.matching.enums import RejectionCategory
from app.services.filtering_service import HardFilterService


def _make_job(title: str = "", company: str = "", location: str = "", description: str = "") -> Job:
    """Build a minimal Job instance for filter testing."""
    return Job(
        id=1,
        raw_job_id=1,
        source_id=1,
        url="https://example.com/job",
        title=title,
        company=company,
        location=location,
        description=description,
        normalized_hash="abc",
    )


def _service() -> HardFilterService:
    """Return a HardFilterService with default rules."""
    return HardFilterService(FilterRules())


def _reasons(result: tuple[RejectionReason, ...]) -> set[str]:
    """Extract category values from rejection reasons."""
    return {r.category.value for r in result}


def test_filter_passes_for_pfe_internship() -> None:
    """A job mentioning PFE in the title should pass all filters."""
    job = _make_job(
        title="PFE Software Engineering Internship", description="Build APIs with Python."
    )
    result = _service().evaluate(job)
    assert result.passed is True
    assert len(result.rejection_reasons) == 0


def test_filter_passes_for_stage_description() -> None:
    """A job with stage keywords in the description should pass the PFE filter."""
    job = _make_job(title="Developpeur Fullstack", description="Stage PFE en developpement web.")
    result = _service().evaluate(job)
    accepted = result.passed
    has_pfe_rejection = any(
        r.category == RejectionCategory.NOT_PFE for r in result.rejection_reasons
    )
    assert accepted or not has_pfe_rejection


def test_filter_rejects_fulltime_without_internship_signals() -> None:
    """A full-time role without internship keywords should be rejected."""
    job = _make_job(title="Software Engineer CDI", description="Full-time permanent position.")
    result = _service().evaluate(job)
    assert result.passed is False
    categories = _reasons(result.rejection_reasons)
    assert RejectionCategory.NOT_PFE.value in categories


def test_filter_rejects_senior_title() -> None:
    """A role with senior-level title should be rejected."""
    job = _make_job(title="Senior Software Engineer", description="PFE internship available.")
    result = _service().evaluate(job)
    assert result.passed is False
    categories = _reasons(result.rejection_reasons)
    assert RejectionCategory.SENIORITY_TOO_HIGH.value in categories


def test_filter_rejects_lead_title() -> None:
    """A role with 'Lead' in the title should be rejected."""
    job = _make_job(title="Lead Developer", description="Internship")
    result = _service().evaluate(job)
    assert result.passed is False
    categories = _reasons(result.rejection_reasons)
    assert RejectionCategory.SENIORITY_TOO_HIGH.value in categories


def test_filter_rejects_blacklisted_location() -> None:
    """A job located in a blacklisted country should be rejected."""
    job = _make_job(title="PFE Internship", location="United States", description="Internship")
    result = _service().evaluate(job)
    assert result.passed is False
    categories = _reasons(result.rejection_reasons)
    assert RejectionCategory.LOCATION_MISMATCH.value in categories


def test_filter_passes_remote_location() -> None:
    """A remote job should pass location filtering."""
    job = _make_job(
        title="PFE Internship", location="Remote", description="Build software APIs with Python."
    )
    result = _service().evaluate(job)
    assert result.passed is True


def test_filter_rejects_non_cs_field() -> None:
    """A job unrelated to computer science should be rejected."""
    job = _make_job(
        title="Marketing Internship",
        description="Help with social media campaigns and brand strategy.",
    )
    result = _service().evaluate(job)
    assert result.passed is False
    categories = _reasons(result.rejection_reasons)
    assert RejectionCategory.NOT_CS_FIELD.value in categories


def test_filter_passes_cs_keywords_in_description() -> None:
    """CS keywords in the description should allow the job through."""
    job = _make_job(title="Internship", description="Python backend development with databases.")
    result = _service().evaluate(job)
    assert result.passed is True


def test_filter_collects_multiple_rejection_reasons() -> None:
    """A job that fails multiple filters should report all reasons."""
    job = _make_job(
        title="Senior Marketing Manager CDI",
        location="USA",
        description="Full-time permanent role leading marketing campaigns.",
    )
    result = _service().evaluate(job)
    categories = _reasons(result.rejection_reasons)
    assert RejectionCategory.NOT_PFE.value in categories
    assert RejectionCategory.SENIORITY_TOO_HIGH.value in categories
    assert RejectionCategory.LOCATION_MISMATCH.value in categories
    assert RejectionCategory.NOT_CS_FIELD.value in categories
    assert RejectionCategory.EMPLOYMENT_TYPE.value in categories


def test_each_rejection_reason_has_detail() -> None:
    """Every rejection reason should include a human-readable detail."""
    job = _make_job(title="Senior Marketing Manager CDI", location="USA")
    result = _service().evaluate(job)
    for reason in result.rejection_reasons:
        assert isinstance(reason.detail, str)
        assert len(reason.detail) > 0


def test_filter_passes_tunisia_location() -> None:
    """A job in Tunisia should pass location filtering."""
    job = _make_job(
        title="Software PFE Internship",
        location="Tunis, Tunisia",
        description="Python backend CS internship.",
    )
    result = _service().evaluate(job)
    assert result.passed is True


def test_filter_passes_france_location() -> None:
    """A job in France should pass location filtering."""
    job = _make_job(
        title="Stage PFE",
        location="Paris, France",
        description="Stage en informatique developpement logiciel et programmation web.",
    )
    result = _service().evaluate(job)
    assert result.passed is True
