from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.job_filter import JobFilter
from app.db.models.jobs import Job
from app.domain.job_filters.entities import (
    JobFilterRejection,
    JobFilterResult,
    JobFilterRules,
)
from app.domain.job_filters.enums import JobFilterRejectionCode

_SINGLETON_ID = 1

_REMOTE_HINTS = (
    "remote",
    "teletravail",
    "work from home",
    "wfh",
    "home office",
    "distantiel",
    "hybrid",
    "mixte",
)

_SENIORITY_HINTS = (
    "executive",
    "director",
    "vp",
    "chief",
    "head of",
    "principal",
    "staff",
    "lead",
    "senior",
    "mid-senior",
    "manager",
)

_CURRENCY_BY_SYMBOL = {"$": "usd", "\u20ac": "eur", "\u00a3": "gbp", "\u20b9": "inr"}


def load_job_filter_rules(session: Session) -> JobFilterRules:
    """Load the persisted user filter rules, defaulting to an empty config."""
    record = session.get(JobFilter, _SINGLETON_ID)
    if record is None or not record.rules_json:
        return JobFilterRules()
    return JobFilterRules.model_validate(record.rules_json)


def save_job_filter_rules(session: Session, rules: JobFilterRules) -> JobFilter:
    """Upsert the singleton filter configuration row."""
    record = session.get(JobFilter, _SINGLETON_ID)
    if record is None:
        record = JobFilter(id=_SINGLETON_ID, rules_json=rules.model_dump())
        session.add(record)
    else:
        record.rules_json = rules.model_dump()
    session.commit()
    return record


class UserFilterService:
    """Apply the user-persisted hard filter stage to a single job.

    The filter is deliberately hard-only and deterministic: it rejects or
    accepts a job based on explicit rule matches and never ranks or scores.
    Rules are evaluated in a fixed precedence order and the first failing rule
    produces the rejection (deterministic first-wins).
    """

    def __init__(self, session: Session, rules: JobFilterRules | None = None) -> None:
        """Initialize with rules loaded from the database unless injected."""
        self._session = session
        self._rules = rules if rules is not None else load_job_filter_rules(session)

    def evaluate(self, job: Job) -> JobFilterResult:
        """Evaluate the user filter against one job."""
        rules = self._rules
        if rules.is_empty():
            return JobFilterResult(passed=True)

        title = job.title or ""
        company = job.company or ""
        location = job.location or ""
        combined = " ".join(
            part for part in (title, job.description, job.requirements) if part
        ).lower()
        source_name = getattr(getattr(job, "source", None), "name", None)

        for check in (
            lambda: self._check_company(company, rules),
            lambda: self._check_title(title, rules),
            lambda: self._check_excluded_keywords(combined, rules),
            lambda: self._check_source(source_name, rules),
            lambda: self._check_location(job, location, rules),
            lambda: self._check_employment_type(job, rules),
            lambda: self._check_seniority(job, title, rules),
            lambda: self._check_salary(job, rules),
            lambda: self._check_required_keywords(combined, rules),
            lambda: self._check_job_age(job, rules),
            lambda: self._check_visa(combined, rules),
        ):
            rejection = check()
            if rejection is not None:
                return JobFilterResult(passed=False, rejections=(rejection,))
        return JobFilterResult(passed=True)

    # -- precedence-ordered checks --------------------------------------

    def _check_company(self, company: str, rules: JobFilterRules) -> JobFilterRejection | None:
        if rules.excluded_companies:
            matched = _contains_any(company, rules.excluded_companies)
            if matched:
                return JobFilterRejection(
                    code=JobFilterRejectionCode.EXCLUDED_COMPANY,
                    detail=f"Company is excluded: {company!r}.",
                    matched_value=matched,
                )
        if rules.required_companies:
            if not company:
                return self._unknown(
                    rules,
                    JobFilterRejectionCode.REQUIRED_COMPANY,
                    "Company is required by the filter but unknown.",
                )
            if not _contains_any(company, rules.required_companies):
                return JobFilterRejection(
                    code=JobFilterRejectionCode.REQUIRED_COMPANY,
                    detail=f"Company {company!r} is not in the required list.",
                )
        return None

    def _check_title(self, title: str, rules: JobFilterRules) -> JobFilterRejection | None:
        if rules.excluded_titles:
            matched = _contains_any(title, rules.excluded_titles)
            if matched:
                return JobFilterRejection(
                    code=JobFilterRejectionCode.EXCLUDED_TITLE,
                    detail=f"Title contains an excluded term: {matched!r}.",
                    matched_value=matched,
                )
        if rules.required_titles:
            if not title:
                return self._unknown(
                    rules,
                    JobFilterRejectionCode.REQUIRED_TITLE,
                    "Title is required by the filter but unknown.",
                )
            if not _contains_any(title, rules.required_titles):
                return JobFilterRejection(
                    code=JobFilterRejectionCode.REQUIRED_TITLE,
                    detail=f"Title {title!r} does not contain any required term.",
                )
        return None

    def _check_excluded_keywords(
        self, combined: str, rules: JobFilterRules
    ) -> JobFilterRejection | None:
        if not rules.excluded_keywords:
            return None
        matched = _keyword_in_text(combined, rules.excluded_keywords)
        if matched:
            return JobFilterRejection(
                code=JobFilterRejectionCode.EXCLUDED_KEYWORD,
                detail=f"Job text contains excluded keyword: {matched[0]!r}.",
                matched_value=matched[0],
            )
        return None

    def _check_source(
        self, source_name: str | None, rules: JobFilterRules
    ) -> JobFilterRejection | None:
        if rules.excluded_sources or rules.included_sources:
            if not source_name:
                return None
            name = source_name.lower()
            if rules.excluded_sources:
                matched = any(s.lower() == name for s in rules.excluded_sources)
                if matched:
                    return JobFilterRejection(
                        code=JobFilterRejectionCode.SOURCE_EXCLUDED,
                        detail=f"Source is excluded: {source_name!r}.",
                        matched_value=source_name,
                    )
            if rules.included_sources and not any(
                s.lower() == name for s in rules.included_sources
            ):
                return JobFilterRejection(
                    code=JobFilterRejectionCode.SOURCE_EXCLUDED,
                    detail=f"Source {source_name!r} is not in the included list.",
                )
        return None

    def _check_location(
        self, job: Job, location: str, rules: JobFilterRules
    ) -> JobFilterRejection | None:
        if rules.remote_only and not self._is_remote(job, location):
            return JobFilterRejection(
                code=JobFilterRejectionCode.LOCATION_MISMATCH,
                detail="Only remote jobs are accepted, but this job is not remote.",
            )
        if rules.excluded_locations:
            matched = _contains_any(location, rules.excluded_locations)
            if matched:
                return JobFilterRejection(
                    code=JobFilterRejectionCode.LOCATION_MISMATCH,
                    detail=f"Location is excluded: {location!r}.",
                    matched_value=matched,
                )
        if rules.required_locations:
            if not location:
                return self._unknown(
                    rules,
                    JobFilterRejectionCode.LOCATION_MISMATCH,
                    "Location is required by the filter but unknown.",
                )
            if not _contains_any(location, rules.required_locations):
                return JobFilterRejection(
                    code=JobFilterRejectionCode.LOCATION_MISMATCH,
                    detail=f"Location {location!r} is not in the required list.",
                )
        return None

    def _check_employment_type(self, job: Job, rules: JobFilterRules) -> JobFilterRejection | None:
        value = self._employment_type(job)
        if (
            rules.employment_type_exclude
            and value
            and _contains_any(value, rules.employment_type_exclude)
        ):
            return JobFilterRejection(
                code=JobFilterRejectionCode.EMPLOYMENT_TYPE,
                detail=f"Employment type is excluded: {value!r}.",
                matched_value=value,
            )
        if rules.employment_type_include:
            if not value:
                return self._unknown(
                    rules,
                    JobFilterRejectionCode.EMPLOYMENT_TYPE,
                    "Employment type is required by the filter but unknown.",
                )
            if not _contains_any(value, rules.employment_type_include):
                return JobFilterRejection(
                    code=JobFilterRejectionCode.EMPLOYMENT_TYPE,
                    detail=f"Employment type {value!r} is not in the accepted list.",
                    matched_value=value,
                )
        return None

    def _check_seniority(
        self, job: Job, title: str, rules: JobFilterRules
    ) -> JobFilterRejection | None:
        value = self._seniority(job, title)
        if rules.seniority_exclude and value and _contains_any(value, rules.seniority_exclude):
            return JobFilterRejection(
                code=JobFilterRejectionCode.SENIORITY,
                detail=f"Seniority is excluded: {value!r}.",
                matched_value=value,
            )
        if rules.seniority_include:
            if not value:
                return self._unknown(
                    rules,
                    JobFilterRejectionCode.SENIORITY,
                    "Seniority is required by the filter but unknown.",
                )
            if not _contains_any(value, rules.seniority_include):
                return JobFilterRejection(
                    code=JobFilterRejectionCode.SENIORITY,
                    detail=f"Seniority {value!r} is not in the accepted list.",
                    matched_value=value,
                )
        return None

    def _check_salary(self, job: Job, rules: JobFilterRules) -> JobFilterRejection | None:
        if rules.salary_min is None and rules.salary_max is None:
            return None
        parsed = self._parse_salary(job)
        if parsed is None:
            return self._unknown(
                rules,
                JobFilterRejectionCode.SALARY_TOO_LOW,
                "Salary is required by the filter but unknown.",
            )
        low, high, currency = parsed
        configured = (rules.salary_currency or "").lower()
        if configured and currency and configured != currency:
            # Different currencies: never fabricate a conversion, skip the rule.
            return None
        if rules.salary_min is not None and low < rules.salary_min:
            return JobFilterRejection(
                code=JobFilterRejectionCode.SALARY_TOO_LOW,
                detail=f"Salary floor {low} is below the minimum {rules.salary_min}.",
                matched_value=str(low),
            )
        if rules.salary_max is not None and high > rules.salary_max:
            return JobFilterRejection(
                code=JobFilterRejectionCode.SALARY_TOO_HIGH,
                detail=f"Salary ceiling {high} exceeds the maximum {rules.salary_max}.",
                matched_value=str(high),
            )
        return None

    def _check_required_keywords(
        self, combined: str, rules: JobFilterRules
    ) -> JobFilterRejection | None:
        if not rules.required_keywords:
            return None
        for keyword in rules.required_keywords:
            if not _keyword_in_text(combined, [keyword]):
                return JobFilterRejection(
                    code=JobFilterRejectionCode.REQUIRED_KEYWORD,
                    detail=f"Job text is missing required keyword: {keyword!r}.",
                    matched_value=keyword,
                )
        return None

    def _check_job_age(self, job: Job, rules: JobFilterRules) -> JobFilterRejection | None:
        if rules.max_job_age_days is None:
            return None
        if job.posted_at is None:
            return self._unknown(
                rules,
                JobFilterRejectionCode.JOB_AGE_TOO_OLD,
                "Job posting date is unknown.",
            )
        now = datetime.now(UTC)
        posted = job.posted_at
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=UTC)
        age = now - posted
        if age > timedelta(days=rules.max_job_age_days):
            return JobFilterRejection(
                code=JobFilterRejectionCode.JOB_AGE_TOO_OLD,
                detail=(
                    f"Job is {age.days} days old, older than the "
                    f"{rules.max_job_age_days} day limit."
                ),
                matched_value=str(age.days),
            )
        return None

    def _check_visa(self, combined: str, rules: JobFilterRules) -> JobFilterRejection | None:
        if rules.visa_required_keywords:
            found = _keyword_in_text(combined, rules.visa_required_keywords)
            if not found:
                return JobFilterRejection(
                    code=JobFilterRejectionCode.VISA_MISMATCH,
                    detail="Job does not mention the required visa sponsorship signal.",
                )
        if rules.visa_excluded_keywords:
            found = _keyword_in_text(combined, rules.visa_excluded_keywords)
            if found:
                return JobFilterRejection(
                    code=JobFilterRejectionCode.VISA_MISMATCH,
                    detail=f"Job mentions excluded visa signal: {found[0]!r}.",
                    matched_value=found[0],
                )
        return None

    # -- helpers --------------------------------------------------------

    def _unknown(
        self,
        rules: JobFilterRules,
        code: JobFilterRejectionCode,
        detail: str,
    ) -> JobFilterRejection | None:
        """Resolve the unknown-data policy for a missing job field.

        *accept* -> pass through, *ignore* -> filter skipped, *reject* -> fail.
        The default is accept so missing data never silently excludes a job.
        """
        if rules.unknown_data_policy == "reject":
            return JobFilterRejection(code=code, detail=detail)
        return None

    def _is_remote(self, job: Job, location: str) -> bool:
        work_mode = (job.classification_work_mode or "").lower()
        if work_mode in ("remote", "hybrid"):
            return True
        lowered = location.lower()
        return any(hint in lowered for hint in _REMOTE_HINTS)

    def _employment_type(self, job: Job) -> str | None:
        value = job.employment_type or job.classification_employment_type
        if value:
            return value
        payload = _raw_payload(job)
        return _payload_str(payload, "employment_type")

    def _seniority(self, job: Job, title: str) -> str | None:
        classified = job.classification_seniority
        if classified:
            return classified
        lowered = title.lower()
        for hint in _SENIORITY_HINTS:
            if hint in lowered:
                return hint
        return None

    _SALARY_NUMBER_RE = re.compile(r"\d[\d,.\s]*\s?[kK]?")

    def _parse_salary(self, job: Job) -> tuple[float, float, str | None] | None:
        """Parse a salary string into (low, high, currency) or None.

        Only an explicit figure in the payload is used; ranges are reported as
        their low and high bounds so minimum/maximum rules compare the correct
        edge. Currency is only surfaced when it can be inferred from a symbol
        or an explicit ISO code — never guessed.
        """
        text = _payload_str(_raw_payload(job), "salary")
        if not text:
            return None
        currency = self._salary_currency(text)
        amounts: list[float] = []
        for match in self._SALARY_NUMBER_RE.finditer(text):
            token = match.group(0).strip()
            factor = 1000 if token[-1:].lower() == "k" else 1
            if token[-1:].lower() == "k":
                token = token[:-1]
            cleaned = re.sub(r"[\s,]", "", token)
            try:
                amounts.append(float(cleaned) * factor)
            except ValueError:
                continue
        if not amounts:
            return None
        return min(amounts), max(amounts), currency

    def _salary_currency(self, text: str) -> str | None:
        for symbol, code in _CURRENCY_BY_SYMBOL.items():
            if symbol in text:
                return code
        match = re.search(r"\b(USD|EUR|GBP|INR|TND|MAD|DZD)\b", text, re.IGNORECASE)
        if match:
            return match.group(1).lower()
        return None


def _contains_any(text: str, tokens: list[str]) -> str | None:
    """Return the first case-insensitive substring token found in text."""
    lowered = text.lower()
    for token in tokens:
        if token.lower() and token.lower() in lowered:
            return token
    return None


def _keyword_in_text(text: str, keywords: list[str]) -> list[str]:
    """Return matched keywords using word-boundary matching (like HardFilter)."""
    found: list[str] = []
    for keyword in keywords:
        if not keyword:
            continue
        pattern = re.compile(r"(?<![a-z])" + re.escape(keyword.lower()) + r"(?![a-z])")
        if pattern.search(text.lower()):
            found.append(keyword)
    return found


def _raw_payload(job: Job) -> dict[str, Any]:
    raw_job = getattr(job, "raw_job", None)
    if raw_job is None:
        return {}
    payload = getattr(raw_job, "raw_payload_json", None)
    return payload if isinstance(payload, dict) else {}


def _payload_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value in (None, ""):
        return None
    return str(value)
