# Phase 3: Master Profile Engine

## Overview

Phase 3 delivers the **Master Profile Engine** — a deterministic, rule-based pipeline for importing, normalizing, validating, persisting, versioning, exporting, and managing candidate profiles from resumes in **PDF, DOCX, and Markdown** formats.

The engine processes a resume through seven stages:

| Stage | Component | Responsibility |
|---|---|---|
| **Parse** | `PDFParser` / `DocxParser` / `MarkdownParser` (infrastructure) | Extract raw text from the document |
| **Normalize** | `ProfileNormalizer` (service) | Convert raw text into structured domain entities via section splitting, regex extraction, and keyword matching |
| **Validate** | `ProfileValidator` (service) | Check field validity (email, URL, phone format) and compute a completeness score |
| **Persist** | `ProfileService` (service) | Store normalized data across 11 database tables using a replace-and-version strategy |
| **Version** | `ProfileVersionRecord` (DB) | Create an immutable JSON snapshot on every import with an auto-incrementing version number |
| **Mask (display)** | `pii` utility | Mask PII (email, phone, URLs) when displaying profile data in CLI output |
| **Export** | `ProfileService.export_profile()` (service) | Serialize the current profile to a JSON file |

The engine is **purely deterministic** — no AI models, no LLM calls, no external APIs. Every extraction and validation rule is hand-crafted regex or keyword matching.

---

## Architecture

The Master Profile Engine follows Clean Architecture layering:

```
app/domain/master_profile/    <-- Domain layer: frozen dataclass entities, enums, error types
app/services/                  <-- Application services: normalizer, validator, profile service
app/infrastructure/parsers/    <-- Infrastructure: PDF, DOCX, Markdown parsers + ParserFactory
app/db/models/profile.py       <-- Persistence: 11 SQLAlchemy ORM models
app/cli/commands.py            <-- CLI: 9 profile subcommands
app/utils/pii.py               <-- PII masking utility for safe display
```

### Layer Responsibilities

| Layer | Directory | Role |
|---|---|---|
| **Domain** | `app/domain/master_profile/` | Pure dataclasses with no dependencies. All entities are `frozen=True, slots=True` for immutability. Enums (`ProficiencyLevel`, `RemotePreference`, `InternshipDuration`) define closed sets of valid values. Errors (`ProfileNotFoundError`, `ProfileValidationError`) provide typed exception hierarchy. |
| **Services** | `app/services/` | Orchestration layer. `ProfileNormalizer` converts raw text to domain entities (including awards, publications, nationality, summary). `ProfileValidator` checks correctness and computes completeness. `ProfileService` coordinates parser → normalizer → validator → database persistence, plus multi-profile management (activate, list, delete, edit). |
| **Infrastructure** | `app/infrastructure/parsers/` | `PDFParser` (pdfplumber), `DocxParser` (python-docx), `MarkdownParser` (builtin). `detect_parser()` factory auto-selects the right parser based on file extension. |
| **Persistence** | `app/db/models/profile.py` | 11 SQLAlchemy ORM models mapped to 11 MySQL tables. All child records cascade-delete. |
| **CLI** | `app/cli/commands.py` | Nine subcommands under `stagepilot profile`: `import`, `show`, `export`, `versions`, `edit`, `validate`, `activate`, `list`, `delete`. |
| **PII Masking** | `app/utils/pii.py` | `mask_email()`, `mask_phone()`, `mask_url()`, `mask_profile_dict()` — used by CLI display commands to prevent PII leakage to stdout. |

---

## Schema — 11 Database Tables

### `profiles`

| Column | Type | Notes |
|---|---|---|
| `id` | INT (PK, auto) | Root aggregate identifier |
| `name` | VARCHAR(200) | Human-readable label (e.g. "My Profile v2") |
| `active` | BOOLEAN | Exactly one profile is `TRUE` at any time |
| `created_at` | DATETIME | Server-default `now()` |
| `updated_at` | DATETIME | Updated on persist |

Unlike Phase 3 initial design (singleton row), Phase 7.6 supports **multiple profile rows**, each representing a distinct resume import. The `active` flag selects which profile the pipeline uses. Profile management commands (`activate`, `list`, `delete`) operate on these rows.

### `profile_versions`

| Column | Type | Notes |
|---|---|---|
| `id` | INT (PK, auto) | |
| `profile_id` | INT (FK → profiles.id) | Indexed |
| `version_number` | INT | Auto-incremented per profile |
| `snapshot_json` | JSON | Complete profile snapshot at version creation |
| `completeness_score` | FLOAT | Score at time of import |
| `change_description` | VARCHAR(500) | Optional human-readable description |
| `created_at` | DATETIME | Server-default `now()` |

Unique per profile on `(profile_id, version_number)`.

### `education`, `experience`, `projects`, `skills`, `languages`, `certifications`, `preferences`

Same structure as documented in Phase 3 original design — all child tables with FK to `profiles.id`.

### `awards`

| Column | Type | Notes |
|---|---|---|
| `id` | INT (PK, auto) | |
| `profile_id` | INT (FK → profiles.id) | Indexed |
| `name` | VARCHAR(200) | Required |
| `issuer` | VARCHAR(200) | |
| `date` | DATE | |
| `description` | TEXT | |

### `publications`

| Column | Type | Notes |
|---|---|---|
| `id` | INT (PK, auto) | |
| `profile_id` | INT (FK → profiles.id) | Indexed |
| `title` | VARCHAR(300) | Required |
| `publisher` | VARCHAR(200) | |
| `date` | DATE | |
| `url` | VARCHAR(500) | |
| `description` | TEXT | |

---

## Pipeline

### Processing Flow

```
Resume (PDF / DOCX / Markdown)
    |
    v
 1. detect_parser(file_path)
    |   Auto-detects parser based on file extension
    |   .pdf → PDFParser (pdfplumber)
    |   .docx / .doc → DocxParser (python-docx)
    |   .md / .markdown → MarkdownParser (builtin)
    v
 2. Parser.parse(file_path)
    |   Extracts raw text from all pages/paragraphs
    v
 3. ProfileNormalizer.normalize(raw_text)
    |   a. _split_sections() — detect section headers for
    |      education, experience, projects, skills, languages,
    |      certifications, summary, awards, publications
    |      (case-insensitive, English + French keywords)
    |
    |   b. _extract_personal_info() — first line = name,
    |      regex for email, phone, URLs; nationality detection
    |      via keyword matching in first 20 lines
    |
    |   c. _parse_education / _experience / _projects / _skills
    |      _languages / _certifications / _awards / _publications
    |
    |   Returns: MasterProfile (frozen dataclass)
    v
 4. ProfileValidator.validate(profile)
    |   - Personal info: name required; email/phone/URL format checks
    |   - Education/Experience: required fields + duplicate + date order
    |   - Skills/Certifications/Projects/Languages: duplicates
    |   - Awards: duplicates + name required
    |   - Publications: duplicates + title required
    |
    |   Raises ProfileValidationError if errors found
    v
 5. ProfileService._persist(profile, completeness, description)
    |   a. If no profile row exists, create one (active=True)
    |   b. Replace all child records (delete + re-insert)
    |   c. Compute next version_number
    |   d. Insert ProfileVersionRecord with full snapshot_json
    |   e. Commit
    v
 Database (11 tables updated + new version row)
```

### Active Profile Usage by Pipeline

The `PipelineOrchestrator` loads the active profile via `ProfileService.get_current_profile()` which queries `WHERE active = TRUE`. This profile is used by:

| Pipeline Step | How Active Profile Is Used |
|---|---|
| **RecommendationEngine** | Profile skills, experience, education, preferences → job matching |
| **ResumeTailorService** | Profile content + job description → AI-tailored resume |
| **CoverLetterService** | Profile personal info + job → AI-generated cover letter |
| **Renderer** | All profile sections → rendered PDF/DOCX output |
| **ApprovalService** | Profile snapshot → ApplicationPackage creation |

---

## Domain Entities

### New in Phase 7.6

```python
@dataclass(frozen=True, slots=True)
class Award:
    name: str
    issuer: str | None = None
    date: date | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class Publication:
    title: str
    publisher: str | None = None
    date: date | None = None
    url: str | None = None
    description: str | None = None
```

Updated `PersonalInfo`:
```python
@dataclass(frozen=True, slots=True)
class PersonalInfo:
    full_name: str
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    nationality: str | None = None  # NEW
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    summary: str | None = None  # NEW
```

---

## CLI Reference

Nine subcommands under `stagepilot profile`:

### `import`

Import a resume (PDF, DOCX, or Markdown), normalize, validate, and persist it.

```bash
# Auto-detected format (PDF)
uv run stagepilot profile import path/to/resume.pdf

# DOCX
uv run stagepilot profile import path/to/resume.docx

# Markdown
uv run stagepilot profile import path/to/resume.md

# With change description
uv run stagepilot profile import resume.md --description "Initial import v2"
```

**Output:** JSON with profile metadata (full name, section counts, completeness score).

```
{"completeness_score": 86.7, "status": "imported", ...}
```

### `show`

Display the active profile as JSON (PII fields masked).

```bash
uv run stagepilot profile show
```

PII masking is applied automatically to `email`, `phone`, `linkedin_url`, `github_url`, `portfolio_url` fields before printing.

### `export`

Export the current profile to a JSON file (unmasked, full data).

```bash
uv run stagepilot profile export --output my_profile.json
```

### `versions`

List all profile versions ordered newest-first.

```bash
uv run stagepilot profile versions
```

### `validate`

Validate the active profile. Returns validation errors or completeness score.

```bash
uv run stagepilot profile validate
```

### `edit`

Edit profile metadata (name, summary). Creates a new version when summary is changed.

```bash
# Rename a profile
uv run stagepilot profile edit --name "My Profile v2"

# Update summary
uv run stagepilot profile edit --summary "Updated professional summary"

# Edit a specific profile (by ID)
uv run stagepilot profile edit --profile-id 2 --name "Candidate Profile"
```

### `activate`

Switch the active profile. Deactivates all others.

```bash
uv run stagepilot profile activate 2
```

### `list`

List all profiles with id, name, active flag, completeness score (PII masked).

```bash
uv run stagepilot profile list
```

### `delete`

Delete a profile (and all its child records via cascade).

```bash
uv run stagepilot profile delete 3
```

---

## Completeness Scoring

Updated from Phase 3 to include **awards** and **publications** in the extra category:

| Category | Weight | Scoring Logic |
|---|---|---|
| **Personal Info** | 20% | 6 sub-fields (full_name, email, phone, linkedin, github, portfolio). Each present = 16.67 pts. |
| **Education** | 20% | Binary: 100 if ≥1 entry, 0 otherwise. |
| **Skills** | 20% | Linear: `min(100, count * 10)`. |
| **Experience** | 20% | Binary: 100 if ≥1 entry, 0 otherwise. |
| **Extras** | 20% | 5 sub-categories (projects, certifications, languages, **awards**, **publications**), each worth 20 pts. |

**Total:**
```
total = personal_info_pct * 0.20
      + education_pct      * 0.20
      + skills_pct         * 0.20
      + experience_pct     * 0.20
      + extras_pct         * 0.20
```

Returned as `ProfileCompleteness(score, breakdown, missing_fields)`.

---

## Versioning

Every import or summary edit creates a new **immutable version snapshot**:

1. **Auto-incrementing version_number** — `SELECT MAX(version_number) WHERE profile_id = ? + 1`
2. **Full JSON snapshot** — Entire `MasterProfile` serialized via `to_dict()` and stored as `snapshot_json`
3. **Replace-and-version persist** — All child rows are deleted and re-inserted; prior state is preserved in the latest snapshot
4. **Change descriptions** — Optional string passed via `--description` or auto-generated
5. **Version listing** — `list_versions()` reconstructs each `MasterProfile` from snapshot JSON via `_dict_to_profile()`

---

## PII Masking Utility

`app/utils/pii.py` provides reusable masking helpers:

| Function | Input | Output |
|---|---|---|
| `mask_email("rayen@example.com")` | `"r***n@example.com"` | Local part masked, domain preserved |
| `mask_phone("+21653852323")` | `"+21653******"` | First 5 digits visible, rest masked |
| `mask_url("https://github.com/johndoe")` | `"https://g***e"` | First/last char of host visible |
| `mask_value("email", val)` | Routes to correct masker | Based on key name |

The utility is used by CLI display commands (`show`, `list`) and is designed to be reusable throughout the project for any logging or display that involves PII. **It never modifies stored profile data** — masking is applied only at the output layer.

---

## Design Decisions

### Deterministic Rule-Based Parsing
All parsing is regex and keyword-based. No AI, no LLM, no external APIs. Gives reproducibility, speed (milliseconds), debuggability, and zero cost.

### Multi-Profile Support
Unlike the original singleton design, Phase 7.6 supports multiple profile rows. The `active` flag determines which profile is used by the pipeline. This enables A/B testing of different resumes, gradual improvements, and rollback.

### Parser Factory
`detect_parser()` in `app/infrastructure/parsers/parser_factory.py` auto-selects the correct parser based on file extension. Adding a new format requires only a new parser class and updating the factory — no changes to services or domain.

### PII Masking at Display Layer
PII is masked only when displayed. Stored data, exported files, and internal service methods always work with the original unmasked values. This separation ensures data integrity while protecting privacy in logs and CLI output.

### Clean Architecture
| Layer | Dependencies | Can Import From |
|---|---|---|
| **Domain** | Python stdlib only | Nothing |
| **Services** | Domain + stdlib | Domain layer only |
| **Infrastructure** | Third-party libs (pdfplumber, python-docx) | Domain + ABC interfaces |
| **Persistence** | SQLAlchemy | SQLAlchemy + Domain types |
| **CLI** | Services + Infrastructure + Utils | All layers |
| **Utils** | Python stdlib | Nothing |

---

## Migration

Phase 7.6 includes an Alembic migration (`20260730_add_profile_name_active_awards_publications.py`) that:

1. Adds `name` (VARCHAR(200)) and `active` (BOOLEAN) columns to the `profiles` table
2. Creates `awards` and `publications` tables with FK to `profiles.id`

The migration depends on the prior migration `32a34eb5c804`.
