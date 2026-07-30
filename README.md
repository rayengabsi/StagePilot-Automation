# StagePilot Automation

AI-powered, human-in-the-loop internship automation platform.

## Status

- Phase 0 — Foundation: scaffold, project config, DB, CI, lint — complete.
- Phase 1 — Job Discovery: RSS/Atom ingestion, normalization, CLI — complete.
- Phase 2 — Filtering & Duplicates: deterministic hard filters, 5-strategy duplicate detection, `job_matches` persistence, rejection/duplicate metrics — complete.
- Phase 3 — Master Profile Engine: resume PDF import, deterministic normalization, field validation, completeness scoring, versioned persistence, JSON export — complete.

## Architecture

The project is a modular monolith using Clean Architecture and Domain-Driven Design boundaries. The database contains 13+ tables spanning jobs (Phase 1–2), job matching (Phase 2), and profiles (Phase 3), including `profiles`, `profile_versions`, `education`, `experience`, `projects`, `skills`, `languages`, `certifications`, and `preferences`.

See [`docs/architecture.md`](docs/architecture.md).

## Requirements

- Windows 11
- Python 3.11+
- uv
- MySQL 8.x installed locally
- Git
- VS Code or another editor

## Setup

PowerShell:

```powershell
Copy-Item .env.example .env
uv sync --all-extras --dev
```

Run database migrations:

```bash
uv run alembic upgrade head
```

## Run

```bash
uv run stagepilot
```

## Usage

### Profile Management

Import a resume PDF, normalize, validate, and persist it:

```bash
uv run stagepilot profile import path/to/resume.pdf
```

Show the current profile in JSON:

```bash
uv run stagepilot profile show
```

Export the current profile to a JSON file:

```bash
uv run stagepilot profile export --output profile.json
```

List all profile versions (newest first):

```bash
uv run stagepilot profile versions
```

### Job Discovery & Filtering

Add an RSS or Atom source:

```bash
uv run stagepilot sources add-rss --name "Example Jobs" --url "https://example.com/jobs.xml"
```

List configured sources:

```bash
uv run stagepilot sources list
```

Run discovery once:

```bash
uv run stagepilot discover
```

Backfill Phase 2 match records for existing jobs:

```bash
uv run stagepilot discover --backfill
```

Phase 2 adds a deterministic matching pipeline after ingestion:

- **Hard Filters** — each job is evaluated against five filter categories. Rejected jobs are recorded in `job_matches` with the reason breakdown.
- **Duplicate Detection** — five strategies (external ID, canonical URL, raw content hash, normalized hash, fuzzy title+company) are tried in priority order.
- **Metrics** — each discovery run reports `accepted`, `rejected`, `semantic_duplicates`, `rejection_breakdown`, and `duplicate_strategy_breakdown`.

All matching decisions are persisted in the `job_matches` table — never only in logs.

See [`docs/phase-2-filtering-and-duplicates.md`](docs/phase-2-filtering-and-duplicates.md) for detailed documentation.

Phase 3 profile documentation:

See [`docs/phase-3-master-profile.md`](docs/phase-3-master-profile.md) for detailed documentation.

## Test

```bash
uv run pytest
```

## Lint And Format

```bash
uv run ruff check .
uv run ruff format .
```

## Migrations

Run migrations with:

```bash
uv run alembic revision --autogenerate -m "message"
uv run alembic upgrade head
```

## Project Structure

```
app/
├── cli/
│   └── commands.py                       # All CLI commands (discover, sources, profile)
├── config/
│   ├── logging.py
│   └── settings.py                       # Settings + FilterRules model
├── db/
│   ├── base.py
│   ├── models/
│   │   ├── jobs.py                       # Phase 1: raw_jobs, jobs
│   │   ├── matching.py                   # Phase 2: job_matches
│   │   ├── profile.py                    # Phase 3: 9 ORM models (profiles, profile_versions, education, experience, projects, skills, languages, certifications, preferences)
│   │   └── __init__.py
│   └── session.py
├── domain/
│   ├── master_profile/                   # Phase 3: MasterProfile entities, enums, errors
│   │   ├── entities.py
│   │   ├── enums.py
│   │   └── errors.py
│   └── ... (other domain modules)
├── infrastructure/
│   ├── job_sources/
│   │   ├── registry.py
│   │   └── rss_feed_connector.py
│   └── parsers/                          # Phase 3: ProfileParser ABC + PDF parser
│       ├── abstract.py                   # ProfileParser (ABC)
│       └── pdf_parser.py                 # PDFParser (pdfplumber)
└── services/
    ├── discovery_service.py
    ├── duplicate_detection_service.py
    ├── filtering_service.py
    ├── job_matching_service.py
    ├── job_normalization_service.py
    ├── job_source_repository.py
    ├── profile_normalizer.py             # Phase 3: resume text → MasterProfile
    ├── profile_service.py                # Phase 3: import, export, versioning
    └── profile_validator.py              # Phase 3: validation + completeness scoring
```

## Future Docker Support

Version 1 runs directly on the local Windows development machine. Docker is intentionally not part of Phase 0. The application remains structured so Docker support can be added later without changing domain or application service code.

## Engineering Rules

- Follow Clean Architecture and Domain-Driven Design boundaries.
- Use dependency injection and interfaces for external services.
- Keep Python type-safe with complete type hints.
- Use Ruff for linting and formatting.
- Add docstrings for public functions and classes.
- Add unit tests for every feature.
- Update documentation in every phase.
- Do not implement shortcuts or placeholder business logic.
