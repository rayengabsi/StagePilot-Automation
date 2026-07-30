# StagePilot Automation Architecture

StagePilot Automation is a modular monolith designed around Clean Architecture and Domain-Driven Design boundaries.

## Locked Principles

- The Master Profile is the source of truth for candidate facts.
- Python owns hard filtering, duplicate detection, scoring, status transitions, and email safety.
- AI providers are advisory only and must never override deterministic business rules.
- Every important decision must be persisted and auditable.
- Every application requires explicit human approval before email sending.
- Version 1 is single-user, but the data and module boundaries must allow future SaaS evolution.

## Phase 0 Scope

Phase 0 establishes only the foundation:

- Python project configuration with `uv`.
- Pydantic Settings and `.env` support.
- Structured application logging.
- SQLAlchemy 2.x base and session primitives.
- Alembic migration configuration.
- Ruff, pytest, pre-commit, and GitHub Actions CI.
- Clean folder structure for future domain, service, and infrastructure code.

No business logic is implemented in Phase 0.

## Module Boundaries

```text
app/
├── config/          Runtime configuration and logging
├── db/              SQLAlchemy base, engines, sessions, migrations integration
├── domain/          Pure domain concepts grouped by bounded context
├── services/        Application use cases and orchestration
├── infrastructure/  External services and adapters
├── schemas/         Pydantic request/response/data schemas
├── workers/         Scheduled/background pipeline entry points
├── cli/             Manual operational commands
└── shared/          Cross-cutting utilities
```

Dependencies should point inward. Domain code must not depend on infrastructure adapters.

## Runtime Bootstrap

```text
stagepilot command
      |
      v
create_application_context()
      |
      +--> load Settings
      +--> configure structured logging
      +--> return ApplicationContext
```

The application bootstrap does not connect to MySQL or start external services on import. External connections will be created explicitly by future services.

## Local Development

Version 1 targets direct execution on Windows 11 with Python 3.11+, `uv`, Git, VS Code, and a locally installed MySQL server. Docker is intentionally excluded from Phase 0, while the module boundaries remain compatible with adding containers later.

## Database Portability

Version 1 uses MySQL through SQLAlchemy. The data layer should avoid MySQL-specific behavior unless there is a documented reason. This keeps a future PostgreSQL migration realistic.

## Phase 1 Job Discovery

Phase 1 implements the first working ingestion pipeline:

```text
RSS/Atom Source -> Fetch -> Normalize -> raw_jobs -> jobs -> Structured Logs
```

The pipeline is intentionally limited. It does not perform duplicate detection beyond ingestion safety, hard filtering, scoring, AI analysis, resume generation, approvals, Telegram, or email.

### Persistence

- `job_sources` stores configured external sources.
- `raw_jobs` stores source-specific raw payloads.
- `jobs` stores canonical normalized job rows.

Ingestion duplicate protection uses deterministic SHA-256 hashes and source-scoped database uniqueness constraints.

### Commands

```text
stagepilot sources add-rss --name "..." --url "..."
stagepilot sources list
stagepilot discover
```

### Logging

Discovery emits structured events including `discovery_started`, `source_discovery_started`, `source_fetch_succeeded`, `job_ingested`, `job_duplicate_skipped`, `source_discovery_failed`, and `discovery_completed`.

## Phase 2 Filtering & Duplicates

Phase 2 adds deterministic matching after ingestion and a backfill mechanism for existing jobs.

```text
                   ┌─────────────────────────────┐
                   │       DiscoveredJob          │
                   └──────────┬──────────────────┘
                              │ normalize
                              v
                   ┌─────────────────────────────┐
                   │       NormalizedJob          │
                   └──────────┬──────────────────┘
                              │ ingest (raw_jobs -> jobs)
                              v
                   ┌─────────────────────────────┐
                   │            Job               │
                   └──────────┬──────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              v               v               v
    ┌─────────────────┐ ┌──────────────┐ ┌──────────────┐
    │  Hard Filters   │ │ Duplicate    │ │  Persist     │
    │  • PFE          │ │ Detection    │ │  JobMatch    │
    │  • Location     │ │ • external_id│ │  record      │
    │  • Seniority    │ │ • canonical  │ └──────────────┘
    │  • CS Field     │ │ • raw hash   │
    │  • Employment   │ │ • norm hash  │
    │    Type         │ │ • fuzzy      │
    └─────────────────┘ └──────────────┘
```

### Persistence

- `job_matches` stores one decision record per job (unique on `job_id`).
- Rejection reasons are stored as a JSON array with `category`, `detail`, and `matched_keyword`.
- Duplicate matches record the strategy, confidence, and matched value.

### Backfill

The `--backfill` flag processes all existing jobs that lack a `JobMatch` record. This is safe to run repeatedly; jobs that already have a match record are skipped.

```bash
stagepilot discover --backfill
```
