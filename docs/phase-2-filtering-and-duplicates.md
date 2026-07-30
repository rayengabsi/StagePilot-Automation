# Phase 2: Filtering and Duplicate Detection

## Overview

Phase 2 adds a deterministic matching pipeline that runs after job ingestion. Every ingested job is evaluated through hard filters and duplicate detection, and the result is persisted in the `job_matches` table.

## Architecture

### Services

| Service | File | Responsibility |
|---|---|---|
| `HardFilterService` | `app/services/filtering_service.py` | Apply five deterministic hard filter categories |
| `DuplicateDetectionService` | `app/services/duplicate_detection_service.py` | Detect duplicates using five strategies in priority order |
| `JobMatchingService` | `app/services/job_matching_service.py` | Orchestrate filtering + dedup, persist `JobMatch` records |

### Flow

```
Job (ingested)
  |
  v
HardFilterService.evaluate(job)
  |-- _check_pfe        — must contain internship/PFE signals
  |-- _check_location   — must pass location whitelist/blacklist
  |-- _check_seniority  — must not be senior/lead/principal
  |-- _check_cs_field   — must contain CS/software keywords
  |-- _check_employment_type — must not be full-time/permanent
  |
  v  (if filters pass)
DuplicateDetectionService.find_duplicate(job)
  |-- Strategy 1: EXTERNAL_ID         — exact match on (source_id, external_id)
  |-- Strategy 2: CANONICAL_URL       — exact URL match (not yet implemented)
  |-- Strategy 3: RAW_CONTENT_HASH    — hash of raw payload
  |-- Strategy 4: NORMALIZED_HASH     — SHA-256 of normalized fields
  |-- Strategy 5: FUZZY_TITLE_COMPANY — RapidFuzz ratio ≥ 80 on title + company
  |
  v
JobMatch record persisted
```

## Hard Filters

Five filter categories are applied sequentially. The first rejection reason stops evaluation for that category; all categories always run so multiple reasons can be collected.

### PFE / Internship Check (`NOT_PFE`)

Requires at least one keyword from `pfe_keywords` in title or description. If a `employment_type_blacklist` keyword (e.g. "cdi", "full-time") is found AND no pfe keyword is present, the job is rejected.

**Keywords:** `pfe`, `stage`, `internship`, `intern`, `stagiaire`, `alternance`, etc.

### Location Check (`LOCATION_MISMATCH`)

- If location matches `location_blacklist` (usa, canada, etc.) → rejected.
- If location is not in `location_whitelist` and is not `remote`-like → rejected.
- Empty location is allowed.

### Seniority Check (`SENIORITY_TOO_HIGH`)

Rejects if title or description contains blacklisted seniority keywords: `senior`, `lead`, `principal`, `staff`, `manager`, `director`, etc.

### CS Field Check (`NOT_CS_FIELD`)

Rejects if neither title nor description contains CS/software keywords: `software`, `data`, `backend`, `frontend`, `developer`, `machine learning`, `cloud`, `devops`, `api`, etc.

### Employment Type Check (`NOT_PFE` — same category)

If a full-time/permanent keyword is present (cdi, permanent, full-time) without a matching internship keyword, the job is rejected.

## Two-Layer Duplicate Protection

The pipeline has two independent duplicate-detection layers that operate at different stages.

### Layer 1: Ingestion Duplicates (Phase 1)

Caught during `JobIngestionService.ingest()` before a job enters the matching pipeline. Uses deterministic database constraints:

- **`(source_id, normalized_hash)`** unique constraint on the `jobs` table — same source cannot ingest two jobs with identical normalized content.
- **`(source_id, external_id)`** unique constraint on the `raw_jobs` table — same source cannot ingest two raw records with the same external identifier.

When an ingestion duplicate is detected, the job is **discarded immediately** — it is never normalized, never written to the `jobs` table, and never reaches the Phase 2 matching pipeline. This is why a discovery run may show a high `duplicate_count` alongside an empty `duplicate_strategy_breakdown` — all duplicates were intercepted at the ingestion layer before Phase 2 could evaluate them.

### Layer 2: Semantic Duplicates (Phase 2)

Runs inside `JobMatchingService` after the job has been fully ingested, normalized, and written to the `jobs` table. Only jobs that pass hard filters proceed to semantic duplicate checking. Uses the 5-strategy pipeline below.

## Duplicate Detection (Phase 2)

Five strategies are tried in priority order. The first strategy that returns a match wins.

| Priority | Strategy | Lookup | Matching Logic |
|---|---|---|---|
| 1 | `EXTERNAL_ID` | `(source_id, external_id)` | Exact match |
| 2 | `CANONICAL_URL` | `url` | Normalized URL match (placeholder for future) |
| 3 | `RAW_CONTENT_HASH` | `RawJob.content_hash` | MD5 of raw payload |
| 4 | `NORMALIZED_HASH` | `Job.normalized_hash` | SHA-256 of normalized fields |
| 5 | `FUZZY_TITLE_COMPANY` | Title + Company | RapidFuzz token sort ratio ≥ 80% |

The fuzzy threshold is configurable via `FilterRules.fuzzy_title_threshold` (default 80.0).

## Database Schema

### `job_matches` Table

| Column | Type | Notes |
|---|---|---|
| `id` | INT (PK, auto) | |
| `job_id` | INT (FK → jobs.id, UNIQUE) | One match record per job |
| `hard_filter_ok` | BOOLEAN | `True` if all filters passed |
| `rejection_reasons_json` | JSON | Array of `{category, detail, matched_keyword}` |
| `duplicate_job_id` | INT (FK → jobs.id, nullable) | Existing job if this is a duplicate |
| `duplicate_strategy` | VARCHAR(50) | Strategy name that matched |
| `duplicate_confidence` | FLOAT | Confidence score (1.0 for exact, fuzzy ratio for fuzzy) |
| `duplicate_matched_value` | TEXT | The value that matched |
| `created_at` | DATETIME | |
| `updated_at` | DATETIME | |

Unique constraint: `(source_id, normalized_hash)` on the `jobs` table prevents duplicate normalized jobs per source.

## Configuration

Filter rules are configured via the `FilterRules` model in `app/config/settings.py`. All fields have sensible defaults.

```python
class FilterRules(BaseModel):
    pfe_keywords: list[str]
    location_whitelist: list[str]
    location_blacklist: list[str]
    seniority_blacklist: list[str]
    cs_field_keywords: list[str]
    employment_type_keywords: list[str]
    employment_type_blacklist: list[str]
    remote_keywords: dict[str, list[str]]
    fuzzy_title_threshold: float
```

Override via environment variables with `STAGEPILOT_FILTER_RULES__*` prefix, or modify defaults in `settings.py`.

## Metrics

Each discovery run produces a `DiscoverySummary` with matching metrics:

| Field | Description |
|---|---|
| `accepted` | Jobs that passed all filters |
| `rejected` | Jobs rejected by one or more filters |
| `semantic_duplicates` | Jobs detected as duplicates by the 5-strategy pipeline |
| `rejection_breakdown` | Dict of `category → count` (e.g. `{"not_cs_field": 5, "seniority_too_high": 2}`) |
| `duplicate_strategy_breakdown` | Dict of `strategy → count` (e.g. `{"external_id": 3, "fuzzy_title_company": 1}`) |

## CLI

```bash
# Normal discovery (ingest new jobs + match them)
uv run stagepilot discover

# Backfill — create JobMatch records for existing jobs that lack them
uv run stagepilot discover --backfill
```

The `--backfill` flag is safe to run multiple times. Jobs with existing `JobMatch` records are skipped.

## Future Directions

- Store filter rules in the database instead of configuration
- Add `CANONICAL_URL` strategy implementation
- Add AI-assisted semantic duplicate detection
- Add per-source override capabilities for filter rules
