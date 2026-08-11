from __future__ import annotations

from datetime import datetime, timedelta

from app.db.models.jobs import Job, JobSource, RawJob
from app.domain.job_filters.entities import JobFilterResult, JobFilterRules
from app.domain.job_filters.enums import JobFilterRejectionCode
from app.services.user_filter_service import UserFilterService
from app.shared.time import utc_now


def _make_job(
    *,
    title: str = "Software Engineer Intern",
    company: str = "Acme",
    location: str = "Tunis, Tunisia",
    description: str = "",
    requirements: str = "",
    employment_type: str | None = None,
    classification_employment_type: str | None = None,
    classification_seniority: str | None = None,
    classification_work_mode: str | None = None,
    posted_at: datetime | None = None,
    salary: str | None = None,
    source_name: str | None = "LinkedIn",
) -> Job:
    """Build a minimal transient Job for user-filter testing."""
    job = Job(
        id=1,
        raw_job_id=1,
        source_id=1,
        url="https://example.com/job",
        title=title,
        company=company,
        location=location,
        description=description,
        requirements=requirements,
        employment_type=employment_type,
        classification_employment_type=classification_employment_type,
        classification_seniority=classification_seniority,
        classification_work_mode=classification_work_mode,
        posted_at=posted_at,
        normalized_hash="abc",
    )
    if salary is not None:
        raw = RawJob(
            id=1,
            source_id=1,
            url="https://example.com/job",
            raw_payload_json={"salary": salary},
            content_hash="x",
            discovered_at=utc_now(),
        )
        job.raw_job = raw
    if source_name is not None:
        job.source = JobSource(
            id=1, name=source_name, type="linkedin_mcp", base_url="", config_json={}
        )
    return job


def _service(rules: JobFilterRules) -> UserFilterService:
    return UserFilterService(session=None, rules=rules)


def _code(result: JobFilterResult) -> str | None:
    if not result.rejections:
        return None
    return result.rejections[0].code.value


def test_empty_filters_pass_everything() -> None:
    job = _make_job()
    result = _service(JobFilterRules()).evaluate(job)
    assert result.passed is True
    assert result.rejections == ()


def test_excluded_title_partial_and_case_insensitive() -> None:
    job = _make_job(title="Senior Software Engineer")
    result = _service(JobFilterRules(excluded_titles=["senior"])).evaluate(job)
    assert result.passed is False
    assert _code(result) == JobFilterRejectionCode.EXCLUDED_TITLE.value


def test_required_title_missing() -> None:
    job = _make_job(title="Data Analyst")
    result = _service(JobFilterRules(required_titles=["engineer"])).evaluate(job)
    assert result.passed is False
    assert _code(result) == JobFilterRejectionCode.REQUIRED_TITLE.value


def test_required_title_matching() -> None:
    job = _make_job(title="Software Engineer Intern")
    result = _service(JobFilterRules(required_titles=["engineer"])).evaluate(job)
    assert result.passed is True


def test_excluded_location() -> None:
    job = _make_job(location="Berlin, Germany")
    result = _service(JobFilterRules(excluded_locations=["berlin"])).evaluate(job)
    assert result.passed is False
    assert _code(result) == JobFilterRejectionCode.LOCATION_MISMATCH.value


def test_required_location() -> None:
    job = _make_job(location="Paris, France")
    result = _service(JobFilterRules(required_locations=["paris"])).evaluate(job)
    assert result.passed is True
    job2 = _make_job(location="London, UK")
    result2 = _service(JobFilterRules(required_locations=["paris"])).evaluate(job2)
    assert result2.passed is False


def test_remote_only_accepts_remote_work_mode() -> None:
    job = _make_job(location="Remote", classification_work_mode="remote")
    result = _service(JobFilterRules(remote_only=True)).evaluate(job)
    assert result.passed is True


def test_remote_only_rejects_onsite() -> None:
    job = _make_job(location="Tunis, Tunisia", classification_work_mode="on_site")
    result = _service(JobFilterRules(remote_only=True)).evaluate(job)
    assert result.passed is False
    assert _code(result) == JobFilterRejectionCode.LOCATION_MISMATCH.value


def test_excluded_employment_type() -> None:
    job = _make_job(employment_type="Full-time")
    result = _service(JobFilterRules(employment_type_exclude=["full-time"])).evaluate(job)
    assert result.passed is False
    assert _code(result) == JobFilterRejectionCode.EMPLOYMENT_TYPE.value


def test_required_employment_type() -> None:
    job = _make_job(employment_type="Internship")
    result = _service(JobFilterRules(employment_type_include=["internship"])).evaluate(job)
    assert result.passed is True
    job2 = _make_job(employment_type="Full-time")
    result2 = _service(JobFilterRules(employment_type_include=["internship"])).evaluate(job2)
    assert result2.passed is False


def test_seniority_unknown_accepts_by_default() -> None:
    job = _make_job(title="Software Engineer", classification_seniority=None)
    result = _service(JobFilterRules(seniority_include=["entry"])).evaluate(job)
    assert result.passed is True


def test_seniority_unknown_rejects_when_policy_says_reject() -> None:
    job = _make_job(title="Software Engineer", classification_seniority=None)
    rules = JobFilterRules(seniority_include=["entry"], unknown_data_policy="reject")
    result = _service(rules).evaluate(job)
    assert result.passed is False
    assert _code(result) == JobFilterRejectionCode.SENIORITY.value


def test_seniority_exclude_inferred_from_title() -> None:
    job = _make_job(title="Senior Backend Engineer", classification_seniority=None)
    result = _service(JobFilterRules(seniority_exclude=["senior"])).evaluate(job)
    assert result.passed is False
    assert _code(result) == JobFilterRejectionCode.SENIORITY.value


def test_salary_min_rejects_low_offer() -> None:
    job = _make_job(salary="$40,000 - $50,000 / year")
    result = _service(JobFilterRules(salary_min=60000)).evaluate(job)
    assert result.passed is False
    assert _code(result) == JobFilterRejectionCode.SALARY_TOO_LOW.value


def test_salary_min_accepts_floor() -> None:
    job = _make_job(salary="$60,000 - $70,000 / year")
    result = _service(JobFilterRules(salary_min=60000)).evaluate(job)
    assert result.passed is True


def test_salary_max_rejects_ceiling() -> None:
    job = _make_job(salary="$90,000 - $110,000 / year")
    result = _service(JobFilterRules(salary_max=100000)).evaluate(job)
    assert result.passed is False
    assert _code(result) == JobFilterRejectionCode.SALARY_TOO_HIGH.value


def test_salary_missing_accepts_by_default() -> None:
    job = _make_job(salary=None)
    result = _service(JobFilterRules(salary_min=60000)).evaluate(job)
    assert result.passed is True


def test_salary_missing_rejects_when_policy_says_reject() -> None:
    job = _make_job(salary=None)
    rules = JobFilterRules(salary_min=60000, unknown_data_policy="reject")
    result = _service(rules).evaluate(job)
    assert result.passed is False


def test_salary_currency_mismatch_never_fabricates_conversion() -> None:
    job = _make_job(salary="30 000 € / an")
    result = _service(JobFilterRules(salary_min=80000, salary_currency="usd")).evaluate(job)
    assert result.passed is True


def test_salary_currency_matching_applies() -> None:
    job = _make_job(salary="$40,000 / year")
    result = _service(JobFilterRules(salary_min=60000, salary_currency="usd")).evaluate(job)
    assert result.passed is False


def test_excluded_keyword_word_boundary() -> None:
    job = _make_job(description="We need a senior manager.")
    result = _service(JobFilterRules(excluded_keywords=["manager"])).evaluate(job)
    assert result.passed is False
    assert _code(result) == JobFilterRejectionCode.EXCLUDED_KEYWORD.value


def test_excluded_keyword_partial_word_is_not_rejected() -> None:
    job = _make_job(description="Uses management frameworks daily.")
    result = _service(JobFilterRules(excluded_keywords=["manager"])).evaluate(job)
    assert result.passed is True


def test_required_keywords_all_must_be_present() -> None:
    job = _make_job(description="Python and backend development.")
    result = _service(JobFilterRules(required_keywords=["python", "backend"])).evaluate(job)
    assert result.passed is True
    job2 = _make_job(description="Python development.")
    result2 = _service(JobFilterRules(required_keywords=["python", "backend"])).evaluate(job2)
    assert result2.passed is False
    assert _code(result2) == JobFilterRejectionCode.REQUIRED_KEYWORD.value


def test_excluded_company() -> None:
    job = _make_job(company="Hooli")
    result = _service(JobFilterRules(excluded_companies=["hooli"])).evaluate(job)
    assert result.passed is False
    assert _code(result) == JobFilterRejectionCode.EXCLUDED_COMPANY.value


def test_required_company() -> None:
    job = _make_job(company="Acme")
    result = _service(JobFilterRules(required_companies=["acme"])).evaluate(job)
    assert result.passed is True
    job2 = _make_job(company="Globex")
    result2 = _service(JobFilterRules(required_companies=["acme"])).evaluate(job2)
    assert result2.passed is False
    assert _code(result2) == JobFilterRejectionCode.REQUIRED_COMPANY.value


def test_excluded_source() -> None:
    job = _make_job(source_name="RemoteOK")
    result = _service(JobFilterRules(excluded_sources=["remoteok"])).evaluate(job)
    assert result.passed is False
    assert _code(result) == JobFilterRejectionCode.SOURCE_EXCLUDED.value


def test_included_source_restricts() -> None:
    job = _make_job(source_name="RemoteOK")
    rules = JobFilterRules(included_sources=["linkedin"])
    result = _service(rules).evaluate(job)
    assert result.passed is False
    job2 = _make_job(source_name="LinkedIn")
    result2 = _service(rules).evaluate(job2)
    assert result2.passed is True


def test_job_age_recent_passes() -> None:
    job = _make_job(posted_at=utc_now())
    result = _service(JobFilterRules(max_job_age_days=30)).evaluate(job)
    assert result.passed is True


def test_job_age_old_rejects() -> None:
    job = _make_job(posted_at=utc_now() - timedelta(days=40))
    result = _service(JobFilterRules(max_job_age_days=30)).evaluate(job)
    assert result.passed is False
    assert _code(result) == JobFilterRejectionCode.JOB_AGE_TOO_OLD.value


def test_job_age_missing_accepts_by_default() -> None:
    job = _make_job(posted_at=None)
    result = _service(JobFilterRules(max_job_age_days=30)).evaluate(job)
    assert result.passed is True


def test_job_age_missing_rejects_when_policy_says_reject() -> None:
    job = _make_job(posted_at=None)
    rules = JobFilterRules(max_job_age_days=30, unknown_data_policy="reject")
    result = _service(rules).evaluate(job)
    assert result.passed is False
    assert _code(result) == JobFilterRejectionCode.JOB_AGE_TOO_OLD.value


def test_unknown_policy_ignore_skips_missing_field() -> None:
    job = _make_job(salary=None)
    rules = JobFilterRules(salary_min=60000, unknown_data_policy="ignore")
    result = _service(rules).evaluate(job)
    assert result.passed is True


def test_visa_required_signal() -> None:
    job = _make_job(description="We sponsor work visas.")
    result = _service(JobFilterRules(visa_required_keywords=["sponsor"])).evaluate(job)
    assert result.passed is True
    job2 = _make_job(description="No sponsorship available.")
    result2 = _service(JobFilterRules(visa_required_keywords=["sponsor"])).evaluate(job2)
    assert result2.passed is False
    assert _code(result2) == JobFilterRejectionCode.VISA_MISMATCH.value


def test_multiple_failures_use_deterministic_precedence() -> None:
    job = _make_job(
        title="Senior Data Engineer",
        company="Hooli",
        description="Manager role with low salary.",
        classification_seniority="Senior",
        salary="$40,000 / year",
    )
    rules = JobFilterRules(
        excluded_companies=["hooli"],
        excluded_titles=["senior"],
        excluded_keywords=["manager"],
        salary_min=60000,
    )
    result = _service(rules).evaluate(job)
    assert result.passed is False
    assert _code(result) == JobFilterRejectionCode.EXCLUDED_COMPANY.value
    assert len(result.rejections) == 1
