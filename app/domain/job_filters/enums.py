from __future__ import annotations

from enum import StrEnum


class JobFilterRejectionCode(StrEnum):
    """Structured identifier for one user-filter rejection.

    These codes are the exact keys reported in a discovery run's
    ``filter_rejection_breakdown``. They are distinct from the config-driven
    ``RejectionCategory`` used by ``HardFilterService``: this layer is the
    user-persisted generic filter and must not reuse those concepts.
    """

    EXCLUDED_KEYWORD = "excluded_keyword"
    REQUIRED_KEYWORD = "required_keyword"
    EXCLUDED_TITLE = "excluded_title"
    REQUIRED_TITLE = "required_title"
    EXCLUDED_COMPANY = "excluded_company"
    REQUIRED_COMPANY = "required_company"
    LOCATION_MISMATCH = "location_mismatch"
    EMPLOYMENT_TYPE = "employment_type"
    SENIORITY = "seniority"
    SALARY_TOO_LOW = "salary_too_low"
    SALARY_TOO_HIGH = "salary_too_high"
    VISA_MISMATCH = "visa_mismatch"
    SOURCE_EXCLUDED = "source_excluded"
    JOB_AGE_TOO_OLD = "job_age_too_old"
