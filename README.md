# StagePilot Automation

AI-powered, human-in-the-loop internship automation platform.

## Status

- Phase 0 — Foundation: scaffold, project config, DB, CI, lint — complete.
- Phase 1 — Job Discovery: RSS/Atom ingestion, normalization, CLI — complete.
- Phase 2 — Filtering & Duplicates: deterministic hard filters, 5-strategy duplicate detection, `job_matches` persistence, rejection/duplicate metrics — complete.
- Phase 3 — Master Profile Engine: resume PDF import, deterministic normalization, field validation, completeness scoring, versioned persistence, JSON export — complete.
- Phase 4 — Recommendation Engine: hard-rule gating, 8-category similarity scoring, weighted aggregation, ranking, feedback — complete.
- Phase 5 — AI Intelligence Layer: provider abstraction (ABC + Gemini), 4 versioned prompt templates, AI orchestrator, 4 services (explanation, resume tailoring, cover letter, email), deterministic output validation, token tracking — complete.
- Phase 6 — Resume Rendering & Document Generation Engine: data-driven template system (5 templates), theme system with TOML overrides, PDF generation (reportlab) with selectable text and ATS-friendly formatting, DOCX generation (python-docx) with heading hierarchy, CLI render subcommands — complete.
- Phase 7 — Human Approval Platform: ApplicationPackage entity with immutable snapshots, 8-state approval state machine, ApprovalService (UI-independent, owns all business logic), queue engine with 5 strategies, audit log, snapshot engine, Telegram bot with inline buttons (thin adapter, zero business logic), CLI approval subcommands, 4 new database tables, 63 tests — complete.

## Architecture

The project is a modular monolith using Clean Architecture and Domain-Driven Design boundaries. The database contains 20+ tables spanning jobs (Phase 1–2), job matching (Phase 2), profiles (Phase 3), recommendations & feedback (Phase 4), AI token usage (Phase 5), and approval system (Phase 7). The rendering engine (Phase 6) operates from in-memory profile data.

See [`docs/architecture.md`](docs/architecture.md).

## Requirements

- Windows 11
- Python 3.11+
- uv
- MySQL 8.x installed locally
- Git
- Node.js 18+ (for Web UI)
- LinkedIn MCP server (see below)

## Setup

PowerShell:

```powershell
Copy-Item .env.example .env
uv sync --all-extras --dev
```

Edit `.env` and set:

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
GEMINI_API_KEY=your_gemini_key_here   # optional, for AI features
```

Run database migrations:

```bash
uv run alembic upgrade head
```

### LinkedIn MCP Setup

The LinkedIn integration uses the `linkedin-mcp-server` package. Install and authenticate:

```bash
# Install the MCP server (one-time)
pip install linkedin-mcp-server

# Authenticate with your LinkedIn session
python -m linkedin_mcp_server --login
```

The MCP server uses your local browser profile for authentication. No LinkedIn credentials are stored by StagePilot.

### Telegram Bot Setup

1. Create a bot via [@BotFather](https://t.me/BotFather) on Telegram
2. Copy the bot token into `.env` as `TELEGRAM_BOT_TOKEN`
3. Get your chat ID (message the bot, then check `https://api.telegram.org/bot<TOKEN>/getUpdates`)
4. Add the chat ID to `config/telegram.toml` in `allowed_chat_ids`

## Run

### Backend API

```bash
uv run uvicorn app.api.app:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Frontend Web UI

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

# Start recurring scheduler (edit config/scheduler.toml to enable)
uv run stagepilot scheduler start

# Check status
uv run stagepilot scheduler status

# Stop a running scheduler
uv run stagepilot scheduler stop
```

The scheduler is disabled by default in `config/scheduler.toml`. Set `enabled = true` to allow recurring runs. `scheduler once` works regardless of this setting.

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

Phase 4 recommendation engine documentation:

See [`docs/phase-4-recommendation-engine.md`](docs/phase-4-recommendation-engine.md) for detailed documentation.

Phase 5 AI intelligence layer documentation:

See [`docs/phase-5-ai-intelligence-layer.md`](docs/phase-5-ai-intelligence-layer.md) for detailed documentation.

### Document Rendering

Phase 6 adds professional document generation from your Master Profile:

```bash
# Render resume as PDF (default template: modern)
uv run stagepilot render resume

# Render resume as DOCX
uv run stagepilot render resume --format docx

# Render with a different template in all formats
uv run stagepilot render resume --template executive --format all

# Render a cover letter
uv run stagepilot render cover-letter

# List available templates
uv run stagepilot render templates

# Preview template configuration
uv run stagepilot render preview --template modern
```

Generated documents go to `output/resume.pdf`, `output/resume.docx`, `output/cover_letter.pdf`, `output/cover_letter.docx`.

Five templates are available: `modern`, `executive`, `minimal`, `classic`, `professional`. Templates are pure JSON — adding a new template requires zero code changes.

### Human Approval Platform

Phase 7 guarantees no application is submitted without explicit human approval:

```bash
# View the approval queue
uv run stagepilot approval queue

# List all packages
uv run stagepilot approval list

# Approve a package
uv run stagepilot approval approve 1 --actor "admin" --comment "Looks great"

# Reject a package
uv run stagepilot approval reject 2 --actor "admin" --comment "Wrong field"

# Request revision
uv run stagepilot approval revise 3 --actor "admin" --comment "Update resume"

# Skip a package
uv run stagepilot approval skip 4

# Archive a package
uv run stagepilot approval archive 5

# View package history
uv run stagepilot approval history 1

# Run the Telegram bot
uv run stagepilot telegram run
```

### AI-Powered Features

Phase 5 adds optional AI features for generating human-readable communication from structured recommendation data:

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

AI features require a configured API key in `.env` (`GEMINI_API_KEY`). All AI outputs pass through deterministic validation (prompt injection detection, empty/short rejection, JSON schema checks) before being returned.

### Recommendation Engine

Phase 4 adds deterministic job matching and scoring:

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

All matching weights, hard-rule toggles, and thresholds are configured in `app/config/matching.toml`.

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
├── api/                                  # FastAPI REST API
│   ├── app.py                            # Application factory + CORS
│   ├── errors.py                         # Error handlers (catch-all + domain)
│   ├── routes/                           # health, profile, filters, scheduler, jobs, matches
│   └── schemas.py                        # Pydantic response models
├── cli/
│   └── commands.py                       # All CLI commands (+ approval + telegram)
├── config/
│   ├── ai.toml                           # Phase 5: AI provider/feature config
│   ├── ai_config.py                      # Phase 5: AIConfig frozen dataclass + loader
│   ├── approval.toml                     # Phase 7: Queue/snapshot config
│   ├── approval_config.py                # Phase 7: ApprovalConfig loader
│   ├── logging.py
│   ├── matching.py                       # Phase 4: MatchingConfig frozen dataclass + loader
│   ├── matching.toml                     # Phase 4: scoring weights, thresholds, hard-rule toggles
│   ├── scheduler.toml                    # Scheduler interval and enabled flag
│   ├── scheduler_config.py               # SchedulerConfig loader
│   ├── settings.py                       # Settings + FilterRules model + API keys
│   ├── telegram_config.py                # Phase 7: TelegramConfig loader
│   └── telegram.toml                     # Phase 7: Telegram bot config
├── db/
│   ├── base.py
│   ├── models/
│   │   ├── ai_usage.py                   # Phase 5: TokenUsageRecord (ai_token_usage)
│   │   ├── approval.py                   # Phase 7: 4 ORM models
│   │   ├── jobs.py                       # Phase 1: raw_jobs, jobs
│   │   ├── matching.py                   # Phase 2: job_matches
│   │   ├── profile.py                    # Phase 3: 9 ORM models
│   │   ├── recommendation.py             # Phase 4: RecommendationRecord + FeedbackRecord
│   │   └── __init__.py
│   ├── repositories/
│   │   └── approval.py                   # Phase 7: 4 repositories
│   └── session.py
├── domain/
│   ├── ai/                               # Phase 5: AI entities, enums, errors
│   │   ├── entities.py
│   │   ├── enums.py
│   │   └── errors.py
│   ├── approval/                         # Phase 7: Approval domain
│   │   ├── __init__.py
│   │   ├── entities.py                   # ApplicationPackage, ApprovalEvent, ApprovalComment
│   │   ├── enums.py                      # ApprovalState, QueueStrategy, VALID_TRANSITIONS
│   │   ├── errors.py                     # 9 error classes
│   │   └── package.py                    # Snapshot builder, hash, factory
│   ├── master_profile/                   # Phase 3: MasterProfile entities, enums, errors
│   │   ├── entities.py
│   │   ├── enums.py
│   │   └── errors.py
│   ├── recommendation/                   # Phase 4: Recommendation domain, matcher, scorer, aggregator
│   │   ├── aggregator.py
│   │   ├── entities.py
│   │   ├── enums.py
│   │   ├── errors.py
│   │   ├── matcher.py
│   │   ├── profile_matcher.py
│   │   └── scorer.py
│   └── ... (other domain modules)
├── infrastructure/
│   ├── ai/                               # Phase 5: AI provider abstraction + Gemini
│   │   ├── abstract.py                   # AIProvider (ABC)
│   │   └── gemini_provider.py            # GeminiProvider
│   ├── job_sources/
│   │   ├── registry.py
│   │   └── rss_feed_connector.py
│   ├── parsers/                          # Phase 3: ProfileParser ABC + PDF parser
│   │   ├── abstract.py                   # ProfileParser (ABC)
│   │   └── pdf_parser.py                 # PDFParser (pdfplumber)
│   └── telegram/                         # Phase 7: Telegram client (thin adapter)
│       ├── __init__.py
│       ├── auth.py                       # TelegramAuth (authorization)
│       ├── bot.py                        # Bot runner
│       ├── handlers.py                   # Command + callback handlers
│       └── messages.py                   # Message formatting
├── rendering/                            # Phase 6: Document generation engine
│   ├── __init__.py
│   ├── abstract.py                       # DocumentRenderer (ABC)
│   ├── assets.py                         # Font resolution
│   ├── cover_letter_renderer.py          # Cover letter orchestration
│   ├── docx_renderer.py                  # DOCX rendering (python-docx)
│   ├── models.py                         # RenderContext, DocumentOutput, etc.
│   ├── pdf_renderer.py                   # PDF rendering (reportlab)
│   ├── renderer_factory.py               # Factory + render_document()
│   ├── resume_renderer.py                # Resume orchestration
│   ├── template_loader.py                # TemplateDef + loader (templates/*/template.json)
│   └── theme_loader.py                   # ThemeDef + loader (config/theme.toml)
└── services/
    ├── ai_orchestrator.py                # Phase 5: AI pipeline orchestrator
    ├── approval_service.py               # Phase 7: ALL approval business logic (UI-independent)
    ├── cover_letter_service.py           # Phase 5: cover letter generation
    ├── discovery_service.py
    ├── duplicate_detection_service.py
    ├── email_draft_service.py            # Phase 5: email draft generation
    ├── explanation_service.py            # Phase 5: match explanation generation
    ├── filtering_service.py
    ├── job_matching_service.py
    ├── job_normalization_service.py
    ├── job_source_repository.py
    ├── output_validator.py               # Phase 5: deterministic AI output validation
    ├── profile_normalizer.py             # Phase 3: resume text → MasterProfile
    ├── profile_service.py                # Phase 3: import, export, versioning
    ├── profile_validator.py              # Phase 3: validation + completeness scoring
    ├── prompt_service.py                 # Phase 5: prompt template loading/rendering
    ├── queue_service.py                  # Phase 7: Queue engine (5 strategies)
    ├── recommendation_service.py         # Phase 4: recommendation pipeline orchestration
    ├── resume_tailor_service.py          # Phase 5: resume tailoring
    ├── scheduler_service.py              # Scheduler: recurring pipeline execution
    ├── snapshot_service.py               # Phase 7: Immutable snapshot creation/validation
    └── token_tracker.py                  # Phase 5: AI token usage tracking
frontend/                                 # React + TypeScript + Vite Web UI
├── src/
│   ├── api/client.ts                     # API client (fetch wrapper)
│   ├── components/                       # Table, StatCard, Sidebar
│   ├── pages/                            # Dashboard, Jobs, Matches, Filters, Scheduler, Profile
│   └── test/                             # Vitest unit tests
├── package.json
└── vite.config.ts
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
