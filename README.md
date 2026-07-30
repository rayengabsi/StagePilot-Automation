# StagePilot Automation

AI-powered, human-in-the-loop internship automation platform.

## Status

- Phase 0 — Foundation: scaffold, project config, DB, CI, lint — complete.
- Phase 1 — Job Discovery: RSS/Atom ingestion, normalization, CLI — complete.
- Phase 2 — Filtering & Duplicates: deterministic hard filters, 5-strategy duplicate detection, `job_matches` persistence, rejection/duplicate metrics — complete.

## Architecture

The project is a modular monolith using Clean Architecture and Domain-Driven Design boundaries.

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

## Run

```bash
uv run stagepilot
```

## Job Discovery

Apply migrations before using discovery commands:

```bash
uv run alembic upgrade head
```

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

### Phase 2 Filtering & Duplicates

Phase 2 adds a deterministic matching pipeline after ingestion:

- **Hard Filters** — each job is evaluated against five filter categories. Rejected jobs are recorded in `job_matches` with the reason breakdown.
- **Duplicate Detection** — five strategies (external ID, canonical URL, raw content hash, normalized hash, fuzzy title+company) are tried in priority order.
- **Metrics** — each discovery run reports `accepted`, `rejected`, `semantic_duplicates`, `rejection_breakdown`, and `duplicate_strategy_breakdown`.

All matching decisions are persisted in the `job_matches` table — never only in logs.

See [`docs/phase-2-filtering-and-duplicates.md`](docs/phase-2-filtering-and-duplicates.md) for detailed documentation.

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
