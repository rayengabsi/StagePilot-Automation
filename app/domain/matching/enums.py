from __future__ import annotations

from enum import StrEnum


class DuplicateStrategy(StrEnum):
    """Strategy used to identify a duplicate job."""

    EXTERNAL_ID = "external_id"
    CANONICAL_URL = "canonical_url"
    RAW_CONTENT_HASH = "raw_content_hash"
    NORMALIZED_HASH = "normalized_hash"
    FUZZY_TITLE_COMPANY = "fuzzy_title_company"


class RejectionCategory(StrEnum):
    """Category of a hard-filter rejection reason."""

    NOT_PFE = "not_pfe"
    NOT_CS_FIELD = "not_cs_field"
    LOCATION_MISMATCH = "location_mismatch"
    SENIORITY_TOO_HIGH = "seniority_too_high"
    EMPLOYMENT_TYPE = "employment_type"
    LANGUAGE_MISMATCH = "language_mismatch"
    REMOTE_TYPE = "remote_type"
    DUPLICATE = "duplicate"
