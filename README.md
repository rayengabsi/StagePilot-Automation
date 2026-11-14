# StagePilot Automation

AI-assisted, **human-in-the-loop** internship search and application platform.

StagePilot discovers job offers, removes duplicates, filters and ranks them against your profile, and prepares tailored application documents. **Nothing is ever submitted without explicit human approval.**


<!-- TODO: add the CI badge once you confirm the workflow file name, e.g.:
[![CI](https://github.com/rayengabsi/StagePilot-Automation/actions/workflows/ci.yml/badge.svg)](https://github.com/rayengabsi/StagePilot-Automation/actions) -->

**Stack:** Python 3.11, FastAPI, SQLAlchemy + Alembic, MySQL, React, TypeScript, Vite, Telegram Bot API, Gemini API
**Quality:** 1,000+ automated backend tests, frontend tests (Vitest), Ruff lint and format, GitHub Actions CI

---

## Table of contents

- [Key features](#key-features)
- [How it works](#how-it-works)
- [Data collection](#data-collection)
- [Architecture](#architecture)
- [Responsible use](#responsible-use)
- [Project status](#project-status)
- [Requirements](#requirements)
- [Setup](#setup)
- [Running the application](#running-the-application)
- [Usage](#usage)
- [Tests and code quality](#tests-and-code-quality)
- [Project structure](#project-structure)
- [Engineering principles](#engineering-principles)
- [Roadmap](#roadmap)
- [License](#license)

---

## Key features

- **Job discovery** from RSS/Atom feeds and LinkedIn (through an MCP server), with normalization into a common job model.
- **Duplicate detection** with 5 strategies tried in priority order (external ID, canonical URL, raw content hash, normalized hash, fuzzy title + company).
- **Deterministic hard filters** across 5 categories. Every decision is persisted in the database with its reason, never only in logs.
- **Master Profile engine**: resume PDF import, normalization, validation, completeness scoring, versioned persistence and JSON export.
- **Recommendation engine**: hard-rule gating, 8-category similarity scoring, weighted aggregation, ranking and user feedback. Weights and thresholds are configurable in TOML.
- **AI intelligence layer** (Gemini, behind a provider abstraction): match explanations, resume tailoring, cover letters and email drafts, with versioned prompt templates, deterministic output validation (including prompt-injection detection) and token tracking.
- **Document rendering**: resume and cover letter in PDF (ATS-friendly, selectable text) and DOCX, with 5 data-driven templates and TOML theme overrides.
- **Human approval platform**: immutable application snapshots, an 8-state approval state machine, a queue engine with 5 strategies, an audit log, a Telegram bot with inline buttons and CLI commands.
- **Resilient scheduler**: recurring runs, overlap protection, failure recovery, graceful shutdown and persistent state.
- **Web UI** (React + TypeScript): dashboard, jobs, matches, filters, scheduler and profile pages.

## How it works

```
 Sources (RSS/Atom, LinkedIn MCP)
              │
              ▼
        Ingestion ──► 1. Normalization
                      2. Duplicate detection
                      3. Hard filters (rule-based)
                      4. Profile matching
                      5. Scoring and ranking
                      6. Notifications (Telegram)
                                │
                                ▼
         AI layer ──► tailored documents ──► Human approval ──► (you decide)
```

Each stage persists its output, so every decision can be inspected and replayed.

## Data collection

Job sources are implemented as **pluggable connectors** registered in `app/infrastructure/job_sources/registry.py`. Today the project ships an RSS/Atom connector (`rss_feed_connector.py`) and a LinkedIn integration through the `linkedin-mcp-server` package. New sources, including HTML crawlers, can be added by implementing a connector and registering it, without changing the domain or service layers.

## Architecture

StagePilot is a **modular monolith** built with Clean Architecture and Domain-Driven Design boundaries:

- `domain/` holds entities, enums and business rules, with no framework dependencies.
- `services/` holds application logic. `ApprovalService` owns all approval business logic and is independent of any UI.
- `infrastructure/` holds adapters (AI providers, parsers, job sources, Telegram). The Telegram bot is a thin adapter with no business logic.
- `api/`, `cli/` and `frontend/` are delivery layers on top of the same services.

The database has 20+ tables covering jobs, job matches, profiles, recommendations and feedback, AI token usage and the approval system. The rendering engine works from in-memory profile data.

See `docs/architecture.md` for details.

## Responsible use

- No application is submitted without explicit human approval (Phase 7).
- The LinkedIn integration uses your own local browser session. StagePilot stores no LinkedIn credentials.
- Use it in line with the terms of the platforms you connect to.

## Project status

| Phase | Scope | Status |
|---|---|---|
| 0 | Foundation: scaffold, project config, DB, CI, lint | Complete |
| 1 | Job discovery: RSS/Atom ingestion, normalization, CLI | Complete |
| 2 | Filtering and duplicates: hard filters, 5-strategy duplicate detection, `job_matches` persistence, metrics | Complete |
| 3 | Master Profile engine: resume PDF import, validation, completeness scoring, versioning, JSON export | Complete |
| 4 | Recommendation engine: hard-rule gating, 8-category scoring, aggregation, ranking, feedback | Complete |
| 5 | AI intelligence layer: provider abstraction, 4 prompt templates, orchestrator, 4 services, output validation, token tracking | Complete |
| 6 | Resume rendering and document generation: 5 templates, themes, PDF and DOCX, CLI | Complete |
| 7 | Human approval platform: snapshots, 8-state machine, queue engine, audit log, Telegram bot (63 tests) | Complete |

Detailed documentation for each phase is in `docs/` (for example `docs/phase-2-filtering-and-duplicates.md`, `docs/phase-3-master-profile.md`, `docs/phase-4-recommendation-engine.md`, `docs/phase-5-ai-intelligence-layer.md`).

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- MySQL 8.x installed locally
- Git
- Node.js 18+ (for the web UI)
- LinkedIn MCP server (optional, see below)

> Developed and tested on Windows 11. The bash commands below are the equivalents for macOS/Linux, which have not been verified yet.

## Setup

**PowerShell (Windows):**

```powershell
Copy-Item .env.example .env
uv sync --all-extras --dev
```

**Bash (macOS/Linux):**

```bash
cp .env.example .env
uv sync --all-extras --dev
```

Edit `.env` and set:

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
GEMINI_API_KEY=your_gemini_key_here   # optional, for AI features
```

Run the database migrations:

```bash
uv run alembic upgrade head
```

### LinkedIn MCP setup

The LinkedIn integration uses the `linkedin-mcp-server` package. Install and authenticate:

```bash
# Install the MCP server (one-time)
pip install linkedin-mcp-server

# Authenticate with your LinkedIn session
python -m linkedin_mcp_server --login
```

The MCP server uses your local browser profile for authentication. No LinkedIn credentials are stored by StagePilot.

### Telegram bot setup

1. Create a bot with @BotFather on Telegram.
2. Copy the bot token into `.env` as `TELEGRAM_BOT_TOKEN`.
3. Get your chat ID: message the bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates`.
4. Add the chat ID to `allowed_chat_ids` in `config/telegram.toml`.

## Running the application

### Backend API

```bash
uv run uvicorn app.api.app:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Frontend web UI

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

### Scheduler

```bash
# Run the pipeline once
uv run stagepilot scheduler once

# Start the recurring scheduler (set enabled = true in config/scheduler.toml)
uv run stagepilot scheduler start

# Check status
uv run stagepilot scheduler status

# Stop a running scheduler
uv run stagepilot scheduler stop
```

The scheduler is disabled by default in `config/scheduler.toml`. `scheduler once` works regardless of this setting.

## Usage

### Profile management

```bash
# Import a resume PDF, normalize, validate and persist it
uv run stagepilot profile import path/to/resume.pdf

# Show the current profile as JSON
uv run stagepilot profile show

# Export the current profile to a JSON file
uv run stagepilot profile export --output profile.json

# List all profile versions (newest first)
uv run stagepilot profile versions
```

### Job discovery and filtering

```bash
# Add an RSS or Atom source
uv run stagepilot sources add-rss --name "Example Jobs" --url "https://example.com/jobs.xml"

# List configured sources
uv run stagepilot sources list

# Run discovery once
uv run stagepilot discover

# Backfill match records for existing jobs
uv run stagepilot discover --backfill
```

After ingestion, a deterministic matching pipeline runs:

- **Hard filters:** each job is evaluated against five filter categories. Rejected jobs are recorded in `job_matches` with the reason breakdown.
- **Duplicate detection:** five strategies are tried in priority order.
- **Metrics:** each discovery run reports `accepted`, `rejected`, `semantic_duplicates`, `rejection_breakdown` and `duplicate_strategy_breakdown`.

All matching decisions are persisted in the `job_matches` table. See `docs/phase-2-filtering-and-duplicates.md`.

### Recommendation engine

```bash
# Run recommendations against all qualified jobs
uv run stagepilot recommend

# Top 5 recommendations in table format
uv run stagepilot recommend --top 5

# Output raw JSON
uv run stagepilot recommend --top 10 --json

# List persisted recommendations
uv run stagepilot recommend --list

# Submit feedback on a recommendation
uv run stagepilot feedback 5 --reason wrong_country
uv run stagepilot feedback 12 --reason wrong_technologies --comment "Uses Java but I only work with Python"
```

Matching weights, hard-rule toggles and thresholds are configured in `app/config/matching.toml`.

### AI-powered features

AI features are optional and require `GEMINI_API_KEY` in `.env`. All AI outputs pass through deterministic validation (prompt-injection detection, empty or too-short rejection, JSON schema checks) before they are returned.

```bash
# Generate a match explanation
uv run stagepilot ai explain 1 --job-title "Engineer" --company "Acme"

# Tailor a resume for a specific job
uv run stagepilot ai tailor-resume 1 --job-description "Senior Python developer"

# Generate a cover letter
uv run stagepilot ai cover-letter 1 --company "Acme" --recipient "HR"

# Draft an application email
uv run stagepilot ai email 1 --company "Acme" --job-title "Engineer"

# View token usage and cost analytics
uv run stagepilot ai usage --limit 10

# List available AI prompt templates
uv run stagepilot ai prompts
```

### Document rendering

```bash
# Render the resume as PDF (default template: modern)
uv run stagepilot render resume

# Render the resume as DOCX
uv run stagepilot render resume --format docx

# Render with a different template in all formats
uv run stagepilot render resume --template executive --format all

# Render a cover letter
uv run stagepilot render cover-letter

# List available templates
uv run stagepilot render templates

# Preview a template configuration
uv run stagepilot render preview --template modern
```

Documents are written to `output/`. Five templates are available: modern, executive, minimal, classic and professional. Templates are pure JSON, so adding a new one requires no code changes.

### Human approval platform

```bash
# View the approval queue
uv run stagepilot approval queue

# List all packages
uv run stagepilot approval list

# Approve, reject, request a revision, skip or archive a package
uv run stagepilot approval approve 1 --actor "admin" --comment "Looks great"
uv run stagepilot approval reject 2 --actor "admin" --comment "Wrong field"
uv run stagepilot approval revise 3 --actor "admin" --comment "Update resume"
uv run stagepilot approval skip 4
uv run stagepilot approval archive 5

# View a package's history
uv run stagepilot approval history 1

# Run the Telegram bot
uv run stagepilot telegram run
```

## Tests and code quality

```bash
# Run the backend test suite
uv run pytest

# Lint and format
uv run ruff check .
uv run ruff format .

# Frontend tests
cd frontend && npm test
```

Database migrations:

```bash
uv run alembic revision --autogenerate -m "message"
uv run alembic upgrade head
```

## Project structure

```
app/
├── api/                                  # FastAPI REST API
│   ├── app.py                            # Application factory + CORS
│   ├── errors.py                         # Error handlers (catch-all + domain)
│   ├── routes/                           # health, profile, filters, scheduler, jobs, matches
│   └── schemas.py                        # Pydantic response models
├── cli/
│   └── commands.py                       # All CLI commands (+ approval + telegram)
├── config/
│   ├── ai.toml                           # AI provider/feature config
│   ├── ai_config.py                      # AIConfig frozen dataclass + loader
│   ├── approval.toml                     # Queue/snapshot config
│   ├── approval_config.py                # ApprovalConfig loader
│   ├── logging.py
│   ├── matching.py                       # MatchingConfig frozen dataclass + loader
│   ├── matching.toml                     # Scoring weights, thresholds, hard-rule toggles
│   ├── scheduler.toml                    # Scheduler interval and enabled flag
│   ├── scheduler_config.py               # SchedulerConfig loader
│   ├── settings.py                       # Settings + FilterRules model + API keys
│   ├── telegram_config.py                # TelegramConfig loader
│   └── telegram.toml                     # Telegram bot config
├── db/
│   ├── base.py
│   ├── models/
│   │   ├── ai_usage.py                   # TokenUsageRecord (ai_token_usage)
│   │   ├── approval.py                   # 4 ORM models
│   │   ├── jobs.py                       # raw_jobs, jobs
│   │   ├── matching.py                   # job_matches
│   │   ├── profile.py                    # 9 ORM models
│   │   ├── recommendation.py             # RecommendationRecord + FeedbackRecord
│   │   └── __init__.py
│   ├── repositories/
│   │   └── approval.py                   # 4 repositories
│   └── session.py
├── domain/
│   ├── ai/                               # AI entities, enums, errors
│   ├── approval/                         # ApplicationPackage, ApprovalEvent, state machine, snapshot builder
│   ├── master_profile/                   # MasterProfile entities, enums, errors
│   ├── recommendation/                   # Recommendation domain, matcher, scorer, aggregator
│   └── ...                               # Other domain modules
├── infrastructure/
│   ├── ai/                               # AIProvider (ABC) + GeminiProvider
│   ├── job_sources/                      # Connector registry + RSS/Atom connector
│   ├── parsers/                          # ProfileParser (ABC) + PDFParser (pdfplumber)
│   └── telegram/                         # Thin adapter: auth, bot, handlers, messages
├── rendering/                            # Document generation engine
│   ├── abstract.py                       # DocumentRenderer (ABC)
│   ├── pdf_renderer.py                   # PDF rendering (reportlab)
│   ├── docx_renderer.py                  # DOCX rendering (python-docx)
│   ├── resume_renderer.py                # Resume orchestration
│   ├── cover_letter_renderer.py          # Cover letter orchestration
│   ├── template_loader.py                # Templates (templates/*/template.json)
│   ├── theme_loader.py                   # Themes (config/theme.toml)
│   └── ...                               # assets, models, renderer_factory
└── services/
    ├── approval_service.py               # ALL approval business logic (UI-independent)
    ├── queue_service.py                  # Queue engine (5 strategies)
    ├── snapshot_service.py               # Immutable snapshot creation/validation
    ├── discovery_service.py
    ├── job_normalization_service.py
    ├── duplicate_detection_service.py
    ├── filtering_service.py
    ├── job_matching_service.py
    ├── recommendation_service.py         # Recommendation pipeline orchestration
    ├── profile_service.py                # Import, export, versioning
    ├── profile_normalizer.py             # Resume text → MasterProfile
    ├── profile_validator.py              # Validation + completeness scoring
    ├── ai_orchestrator.py                # AI pipeline orchestrator
    ├── explanation_service.py            # Match explanations
    ├── resume_tailor_service.py          # Resume tailoring
    ├── cover_letter_service.py           # Cover letter generation
    ├── email_draft_service.py            # Email drafts
    ├── prompt_service.py                 # Prompt template loading/rendering
    ├── output_validator.py               # Deterministic AI output validation
    ├── token_tracker.py                  # AI token usage tracking
    ├── scheduler_service.py              # Recurring pipeline execution
    └── job_source_repository.py
frontend/                                 # React + TypeScript + Vite web UI
├── src/
│   ├── api/client.ts                     # API client (fetch wrapper)
│   ├── components/                       # Table, StatCard, Sidebar
│   ├── pages/                            # Dashboard, Jobs, Matches, Filters, Scheduler, Profile
│   └── test/                             # Vitest unit tests
├── package.json
└── vite.config.ts
```

## Engineering principles

- Clean Architecture and Domain-Driven Design boundaries.
- Dependency injection and interfaces for external services (AI providers, parsers, job sources).
- Type-safe Python with complete type hints, linted and formatted with Ruff.
- Docstrings on public functions and classes.
- Unit tests for every feature, and documentation updated with every phase.
- No placeholder business logic: each phase ships complete and tested.

## Roadmap

- Docker support. Version 1 runs directly on the local machine, and the application is structured so Docker can be added without changing domain or service code.
- Additional job-source connectors (including HTML crawlers) through the connector registry.
- Verified macOS/Linux setup.

## License

<!-- TODO: add a LICENSE file (for example MIT) and keep this line -->
MIT
