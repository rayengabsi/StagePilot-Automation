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

## Phase 3 Master Profile Engine

Phase 3 implements the Master Profile Engine for importing, normalizing, validating, persisting, versioning, and exporting candidate profiles from resume PDFs.

See [`docs/phase-3-master-profile.md`](docs/phase-3-master-profile.md) for detailed documentation.

### Persistence (9 tables)

- `profiles` -- singleton root aggregate
- `profile_versions` -- immutable JSON snapshots per import
- `education` -- education history entries
- `experience` -- work experience entries
- `projects` -- project entries
- `skills` -- skill entries with category and proficiency
- `languages` -- language entries with proficiency
- `certifications` -- certification entries
- `preferences` -- one-to-one preferences (countries, cities, remote, technologies, etc.)

### Commands

```text
stagepilot profile import <file> [--description]
stagepilot profile show
stagepilot profile export [--output]
stagepilot profile versions
```

## Phase 4 Recommendation Engine

Phase 4 implements the Recommendation Engine -- a deterministic matching pipeline that scores jobs against the master profile using configurable hard rules, 8-category similarity scoring, and weighted aggregation.

See [`docs/phase-4-recommendation-engine.md`](docs/phase-4-recommendation-engine.md) for detailed documentation.

```text
                     MasterProfile
                          |
                          v
      +--------------------------------------+
      |     ProfileMatcher (orchestrator)     |
      |                                       |
      |  +----------------+  +-------------+  |
      |  | HardRuleMatcher|  |Similarity   |  |
      |  |  - country     |  |Scorer       |  |
      |  |  - work mode   |  |  - 8 cats   |  |
      |  |  - language    |  |  - rapidfuzz|  |
      |  +-------+--------+  +------+------+  |
      |          |                  |          |
      |          v                  v          |
      |  +----------------+  +-------------+  |
      |  | HardRuleResult |  |ScoreBreakdown|  |
      |  +----------------+  +------+------+  |
      |                             |          |
      |                             v          |
      |                    +-------------+     |
      |                    | ScoreAggreg |     |
      |                    |  (weighted) |     |
      |                    +------+------+     |
      |                           |            |
      +---------------------------|------------+
                                 v
                          Recommendation
                     (persisted to database)
```

### Persistence (2 new tables)

- `recommendations` -- stores final_score, ranking_position, status, 6 JSON columns for matched/missing items, score_breakdown_json, hard_rule results
- `recommendation_feedback` -- stores user feedback per recommendation (reason + optional comment)

### Commands

```text
stagepilot recommend [--top N] [--json] [--list]
stagepilot feedback <id> --reason <reason> [--comment <text>]
```

### Configuration

All scoring weights, thresholds, hard-rule toggles, and the fuzz threshold are configured in `app/config/matching.toml`. No weights are hardcoded in Python.
