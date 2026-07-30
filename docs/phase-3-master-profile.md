# Phase 3: Master Profile Engine

## Overview

Phase 3 delivers the **Master Profile Engine** — a deterministic, rule-based pipeline for importing, normalizing, validating, persisting, versioning, and exporting candidate profiles from resume PDFs. The engine processes a resume through six stages:

| Stage | Component | Responsibility |
|---|---|---|
| **Import** | `PDFParser` (infrastructure) | Extract raw text from a PDF resume |
| **Normalize** | `ProfileNormalizer` (service) | Convert raw text into structured domain entities via section splitting, regex extraction, and keyword matching |
| **Validate** | `ProfileValidator` (service) | Check field validity (email, URL, phone format) and compute a completeness score |
| **Persist** | `ProfileService` (service) | Store normalized data across 9 database tables using a replace-and-version strategy |
| **Version** | `ProfileVersionRecord` (DB) | Create an immutable JSON snapshot on every import with an auto-incrementing version number |
| **Export** | `ProfileService.export_profile()` (service) | Serialize the current profile to a JSON file |

The engine is **purely deterministic** — no AI models, no LLM calls, no external APIs. Every extraction and validation rule is hand-crafted regex or keyword matching.

---

## Architecture

The Master Profile Engine follows the same Clean Architecture layering as the rest of the project:

```
app/domain/master_profile/    <-- Domain layer: frozen dataclass entities, enums, error types
app/services/                  <-- Application services: normalizer, validator, profile service
app/infrastructure/parsers/    <-- Infrastructure: PDF parser implementing ProfileParser ABC
app/db/models/profile.py       <-- Persistence: 9 SQLAlchemy ORM models
app/cli/commands.py            <-- CLI: 4 profile subcommands (import, show, export, versions)
```

### Layer Responsibilities

| Layer | Directory | Role |
|---|---|---|
| **Domain** | `app/domain/master_profile/` | Pure dataclasses with no dependencies on frameworks or databases. All entities are `frozen=True, slots=True` for immutability and memory efficiency. Domain enums (`ProficiencyLevel`, `RemotePreference`, `InternshipDuration`, `SkillCategory`) define closed sets of valid values. Domain errors (`MasterProfileError`, `ProfileNotFoundError`, `ProfileImportError`, `ProfileValidationError`) provide typed exception hierarchy. |
| **Services** | `app/services/` | Orchestration layer. `ProfileNormalizer` converts raw text to domain entities. `ProfileValidator` checks correctness and computes completeness. `ProfileService` coordinates parser → normalizer → validator → database persistence. |
| **Infrastructure** | `app/infrastructure/parsers/` | Concrete implementations of the `ProfileParser` ABC. Currently only `PDFParser` (backed by `pdfplumber`), but the interface supports future formats (DOCX, HTML, TXT). |
| **Persistence** | `app/db/models/profile.py` | SQLAlchemy ORM models mapped to 9 MySQL tables. All child records cascade-delete from the parent `profiles` row. |
| **CLI** | `app/cli/commands.py` | Four subcommands under `stagepilot profile`: `import`, `show`, `export`, `versions`. |

---

## Schema — 9 Database Tables

The profile data is stored across 9 related tables. All child tables reference `profiles.id` via a foreign key and cascade on delete.

### `profiles`

| Column | Type | Notes |
|---|---|---|
| `id` | INT (PK, auto) | Root aggregate identifier |
| `created_at` | DATETIME | Server-default `now()` |
| `updated_at` | DATETIME | Updated on every persist |

There is exactly **one** row in this table at any time. Each import replaces child records and creates a new version row.

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

Unique per profile on `(profile_id, version_number)` — no two versions share the same number.

### `education`

| Column | Type | Notes |
|---|---|---|
| `id` | INT (PK, auto) | |
| `profile_id` | INT (FK → profiles.id) | Indexed |
| `institution` | VARCHAR(200) | Required |
| `degree` | VARCHAR(100) | |
| `field_of_study` | VARCHAR(200) | |
| `start_date` | DATE | |
| `end_date` | DATE | |
| `gpa` | VARCHAR(20) | |
| `description` | TEXT | |

### `experience`

| Column | Type | Notes |
|---|---|---|
| `id` | INT (PK, auto) | |
| `profile_id` | INT (FK → profiles.id) | Indexed |
| `company` | VARCHAR(200) | Required |
| `title` | VARCHAR(200) | |
| `location` | VARCHAR(200) | |
| `start_date` | DATE | |
| `end_date` | DATE | |
| `is_current` | BOOLEAN | Default `False` |
| `description` | TEXT | |
| `technologies_json` | JSON | Array of technology strings |

### `projects`

| Column | Type | Notes |
|---|---|---|
| `id` | INT (PK, auto) | |
| `profile_id` | INT (FK → profiles.id) | Indexed |
| `name` | VARCHAR(200) | Required |
| `description` | TEXT | |
| `url` | VARCHAR(500) | |
| `technologies_json` | JSON | Array of technology strings |
| `start_date` | DATE | |
| `end_date` | DATE | |

### `skills`

| Column | Type | Notes |
|---|---|---|
| `id` | INT (PK, auto) | |
| `profile_id` | INT (FK → profiles.id) | Indexed |
| `name` | VARCHAR(100) | Required |
| `category` | VARCHAR(50) | e.g. `programming_language`, `framework`, `cloud` |
| `proficiency` | VARCHAR(20) | One of `native`, `fluent`, `advanced`, `intermediate`, `basic` |

### `languages`

| Column | Type | Notes |
|---|---|---|
| `id` | INT (PK, auto) | |
| `profile_id` | INT (FK → profiles.id) | Indexed |
| `name` | VARCHAR(100) | Required |
| `proficiency` | VARCHAR(20) | Same proficiency enum as skills |

### `certifications`

| Column | Type | Notes |
|---|---|---|
| `id` | INT (PK, auto) | |
| `profile_id` | INT (FK → profiles.id) | Indexed |
| `name` | VARCHAR(200) | Required |
| `issuer` | VARCHAR(200) | |
| `date` | DATE | |
| `url` | VARCHAR(500) | |

### `preferences`

| Column | Type | Notes |
|---|---|---|
| `id` | INT (PK, auto) | |
| `profile_id` | INT (FK → profiles.id) | **Unique** — one-to-one with profiles |
| `preferred_countries_json` | JSON | Array of country names |
| `preferred_cities_json` | JSON | Array of city names |
| `remote_preference` | VARCHAR(20) | `remote`, `hybrid`, `onsite`, `any` |
| `internship_duration` | VARCHAR(20) | `1_month` through `6_months`, `any` |
| `preferred_technologies_json` | JSON | Array of technology strings |
| `preferred_industries_json` | JSON | Array of industry names |
| `preferred_company_size` | VARCHAR(50) | |
| `preferred_language` | VARCHAR(50) | |
| `salary_expectation` | VARCHAR(100) | |

---

## Pipeline

The full processing pipeline flows through these stages:

```
Resume PDF
    |
    v
 1. PDFParser.parse(file_path)
    |   Uses pdfplumber to extract text from every page
    |   Raises FileNotFoundError / ValueError on failure
    v
 Raw text
    |
    v
 2. ProfileNormalizer.normalize(raw_text)
    |   a. _split_sections() — detect section headers (education,
    |      experience, projects, skills, languages, certifications)
    |      using case-insensitive keyword matching in English and French
    |
    |   b. _extract_personal_info() — first line is name, regex for
    |      email, phone, URLs (LinkedIn, GitHub, portfolio)
    |
    |   c. _parse_education() — blank-line blocks, institution from
    |      first line, degree/field via keyword matching
    |
    |   d. _parse_experience() — blank-line blocks, company from
    |      first line, title via role keywords, tech via tech keywords
    |
    |   e. _parse_projects() — blank-line blocks, name from first line,
    |      tech via keyword matching, URL extraction
    |
    |   f. _parse_skills() — split on commas, semicolons, bullets, newlines
    |
    |   g. _parse_languages() — split on commas/semicolons, detect
    |      proficiency level from text
    |
    |   h. _parse_certifications() — split on commas/semicolons/newlines
    |
    |   Returns: MasterProfile (frozen dataclass with all sections)
    v
 Normalized MasterProfile
    |
    v
 3. ProfileValidator.validate(profile)
    |   - Personal info: full_name required; email, phone, URL format checks
    |   - Education: institution required; duplicate detection; date ordering
    |   - Experience: company required; duplicate detection; date ordering
    |   - Skills: name required; duplicate detection
    |   - Certifications: name required; duplicate detection
    |   - Projects: name required; duplicate detection; URL format check
    |   - Languages: name required; duplicate detection
    |
    |   Raises ProfileValidationError if any errors found
    v
 Validated MasterProfile
    |
    v
 4. ProfileValidator.compute_completeness(profile)
    |   Returns ProfileCompleteness with score, breakdown, missing_fields
    v
 5. ProfileService._persist(profile, completeness, description)
    |   a. Ensure profiles row exists (singleton)
    |   b. Delete all child records (education, experience, etc.)
    |   c. Insert new child records from the normalized profile
    |   d. Compute next version_number (max existing + 1)
    |   e. Insert ProfileVersionRecord with full snapshot_json
    |   f. Commit transaction
    v
 Database (9 tables updated + 1 new version row)
```

---

## CLI

Four subcommands are available under `stagepilot profile`:

### `stagepilot profile import <file>`

Import a resume PDF, normalize, validate, and persist it.

```bash
# Basic import
uv run stagepilot profile import path/to/resume.pdf

# Import with a change description for the version history
uv run stagepilot profile import path/to/resume.pdf --description "Initial import v2"
```

**Output:** JSON with profile metadata (full name, section counts, completeness score).

```
{"completeness_breakdown": {"education": 100.0, "experience": 100.0, "personal_info": 66.7, "projects_certifications_languages": 66.7, "skills": 100.0}, "completeness_score": 86.7, "education_count": 2, "experience_count": 3, "full_name": "John Doe", "languages_count": 2, "missing_fields": ["github_url", "portfolio_url"], "projects_count": 1, "skills_count": 10, "status": "imported"}
```

### `stagepilot profile show`

Display the current profile as JSON.

```bash
uv run stagepilot profile show
```

Outputs the full profile including completeness metadata.

### `stagepilot profile export [--output]`

Export the current profile to a JSON file.

```bash
# Default output file
uv run stagepilot profile export

# Custom output path
uv run stagepilot profile export --output my_profile.json
```

### `stagepilot profile versions`

List all profile versions ordered newest-first.

```bash
uv run stagepilot profile versions
```

**Output:** JSON array with version number, completeness score, change description, and creation timestamp.

```json
[
  {
    "version": 2,
    "completeness_score": 86.7,
    "change_description": "Imported from resume_v2.pdf",
    "created_at": "2026-07-30T12:00:00+00:00",
    "full_name": "John Doe"
  },
  {
    "version": 1,
    "completeness_score": 73.3,
    "change_description": "Imported from resume_v1.pdf",
    "created_at": "2026-07-29T12:00:00+00:00",
    "full_name": "John Doe"
  }
]
```

---

## Completeness Scoring

The `ProfileValidator.compute_completeness()` method calculates a score from 0–100 based on five equally-weighted categories. Each category contributes **20%** to the total.

### Category Breakdown

| Category | Weight | Scoring Logic |
|---|---|---|
| **Personal Info** | 20% | 6 sub-fields (full_name, email, phone, linkedin_url, github_url, portfolio_url). Each present field contributes 16.67 points. Max: 100. |
| **Education** | 20% | Binary: 100 if at least one education entry exists, 0 otherwise. |
| **Skills** | 20% | Linear: `min(100, count * 10)`. 1 skill = 10 pts, 10+ skills = 100 pts. |
| **Experience** | 20% | Binary: 100 if at least one experience entry exists, 0 otherwise. |
| **Projects / Certifications / Languages** | 20% | 3 sub-categories (projects, certifications, languages), each worth 33.33 points. 100 if all three sections have data. |

**Total formula:**
```
total = personal_info_pct * 0.20
      + education_pct       * 0.20
      + skills_pct          * 0.20
      + experience_pct      * 0.20
      + extra_pct           * 0.20
```

The result is returned as a `ProfileCompleteness` dataclass with:
- `score` — Float 0–100
- `breakdown` — Dict of category → percentage (e.g. `{"personal_info": 66.7, "education": 100.0, ...}`)
- `missing_fields` — Tuple of field/section names that are empty

Missing fields are reported across all five categories so the user knows exactly which sections need improvement.

---

## Versioning

Every import creates a new **immutable version snapshot**. The versioning system works as follows:

1. **Auto-incrementing version_number** — `ProfileService._next_version_number()` queries `SELECT MAX(version_number) WHERE profile_id = ?` and adds 1. The first import gets version 1, the second gets version 2, and so on.

2. **Full JSON snapshot** — The entire `MasterProfile` is serialized via `to_dict()` and stored as `snapshot_json` in the `profile_versions` table. This preserves the exact state at the time of import, independent of any subsequent changes to child records.

3. **Replace-and-version persist strategy** — When a profile is imported, all child rows (education, experience, skills, projects, languages, certifications, preferences) are **deleted** and **re-inserted** from the new normalized data. This is a replace operation. The previous state is not lost because it is captured in the latest version snapshot.

4. **Change descriptions** — Each version can carry an optional `change_description` string (passed via `--description` on the CLI) to document what changed.

5. **Version listing** — `stagepilot profile versions` returns all versions ordered by `version_number DESC`, reconstructing the `MasterProfile` from each snapshot JSON.

### Version Table Structure

```sql
CREATE TABLE profile_versions (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    profile_id      INT NOT NULL,
    version_number  INT NOT NULL,
    snapshot_json   JSON NOT NULL,
    completeness_score FLOAT NOT NULL DEFAULT 0.0,
    change_description VARCHAR(500),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES profiles(id),
    UNIQUE (profile_id, version_number)
);
```

Each version is append-only. Old versions are never modified or deleted.

---

## Design Decisions

### No AI — Purely Deterministic Rule-Based Parsing

The entire normalizer uses hand-crafted regex patterns, keyword lists, and section header detection. There is no machine learning, no LLM API call, and no external NLP service. This choice is deliberate:

- **Reproducibility** — The same input always produces the same output.
- **Speed** — Parsing completes in milliseconds, and requires no GPU or network access.
- **Debuggability** — Every extraction decision can be traced to a specific regex or keyword match.
- **Zero cost** — No API tokens, no model hosting, no usage limits.

**Trade-off:** Rule-based parsing is less robust than AI for unusual resume formats or unconventional layouts. The normalizer handles standard resume structures well (section headers, bullet points, chronological order) but may miss data in highly customized layouts.

### Clean Architecture

The Master Profile Engine follows strict Clean Architecture boundaries:

| Layer | Dependencies | Can Import From |
|---|---|---|
| **Domain** (`entities.py`, `enums.py`, `errors.py`) | Python stdlib only | Nothing |
| **Services** (`profile_normalizer.py`, `profile_validator.py`, `profile_service.py`) | Domain + stdlib | Domain layer only |
| **Infrastructure** (`pdf_parser.py`) | Third-party libs (pdfplumber) | Domain + ABC interfaces |
| **Persistence** (`profile.py` ORM models) | SQLAlchemy | SQLAlchemy + Domain types |
| **CLI** (`commands.py`) | Services + Infrastructure | All layers |

Domain entities are pure Python `@dataclass(frozen=True, slots=True)` with zero framework dependencies. They can be unit-tested without a database or parser.

### Frozen Dataclasses for Domain Entities

All domain entities (`PersonalInfo`, `Education`, `Experience`, `Project`, `Skill`, `Language`, `Certification`, `Preference`, `MasterProfile`, `ProfileVersion`, `ProfileCompleteness`) are:

- **`frozen=True`** — Immutable after creation. Prevents accidental mutation and makes them safe to use as dictionary keys or in sets.
- **`slots=True`** — Reduces memory overhead by avoiding `__dict__` per instance. Important when handling profiles with many education/experience/skill entries.

### Two-Layer Duplicate Protection (Cross-Phase)

While Phase 2’s two-layer duplicate protection operates on jobs at the ingestion and semantic levels, Phase 3 adds a separate duplicate detection within the profile validator:

- **Duplicate entries within a section** — The validator checks for duplicate education entries (same institution + degree + field), duplicate experience entries (company + title), duplicate skills, certifications, projects, and languages. These are reported as validation errors and prevent import.
- **No cross-profile duplicate detection** — The engine assumes each user manages a single profile. There is no deduplication between different resume imports — each import creates a new version, and the previous data is replaced, not merged.

### Preference Defaults

The `Preference` entity uses sensible defaults:
- `RemotePreference.ANY` — No remote preference bias
- `InternshipDuration.ANY` — No duration restriction
- Empty tuples for preferred countries, cities, technologies, industries

These are set during normalization and can be updated via future API endpoints or CLI commands.

### Parser Extensibility

The `ProfileParser` abstract base class defines a single method `parse(file_path: Path) -> str`. This interface allows adding new parsers for different document formats without changing any service or domain code:

- `PDFParser` — Current implementation using `pdfplumber`
- Future: `DOCXParser`, `HTMLParser`, `TxtParser`, `MarkdownParser`

All parsers return raw text. Normalization is handled entirely by `ProfileNormalizer`, keeping the infrastructure layer thin.

---

## Future Directions

- Add DOCX and HTML parser implementations
- Expose preference editing via CLI (`stagepilot profile set-preference`)
- Add profile diff between versions (`stagepilot profile diff --v1 --v2`)
- Implement profile merge strategies for incremental resume updates
- Add export to additional formats (YAML, Markdown, HTML)
- Store completeness history over time for trend visualization
