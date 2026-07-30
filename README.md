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

## Architecture

The project is a modular monolith using Clean Architecture and Domain-Driven Design boundaries. The database contains 16+ tables spanning jobs (Phase 1–2), job matching (Phase 2), profiles (Phase 3), recommendations & feedback (Phase 4), and AI token usage (Phase 5). The rendering engine (Phase 6) operates from in-memory profile data and does not require new database tables.

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
├── cli/
│   └── commands.py                       # All CLI commands (discover, sources, profile, recommend, feedback, ai)
├── config/
│   ├── ai.toml                           # Phase 5: AI provider/feature config
│   ├── ai_config.py                      # Phase 5: AIConfig frozen dataclass + loader
│   ├── logging.py
│   ├── matching.py                       # Phase 4: MatchingConfig frozen dataclass + loader
│   ├── matching.toml                     # Phase 4: scoring weights, thresholds, hard-rule toggles
│   └── settings.py                       # Settings + FilterRules model + API keys
├── db/
│   ├── base.py
│   ├── models/
│   │   ├── ai_usage.py                   # Phase 5: TokenUsageRecord (ai_token_usage)
│   │   ├── jobs.py                       # Phase 1: raw_jobs, jobs
│   │   ├── matching.py                   # Phase 2: job_matches
│   │   ├── profile.py                    # Phase 3: 9 ORM models
│   │   ├── recommendation.py             # Phase 4: RecommendationRecord + FeedbackRecord
│   │   └── __init__.py
│   └── session.py
├── domain/
│   ├── ai/                               # Phase 5: AI entities, enums, errors
│   │   ├── entities.py
│   │   ├── enums.py
│   │   └── errors.py
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
│   └── parsers/                          # Phase 3: ProfileParser ABC + PDF parser
│       ├── abstract.py                   # ProfileParser (ABC)
│       └── pdf_parser.py                 # PDFParser (pdfplumber)
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
    ├── recommendation_service.py         # Phase 4: recommendation pipeline orchestration
    ├── resume_tailor_service.py          # Phase 5: resume tailoring
    └── token_tracker.py                  # Phase 5: AI token usage tracking
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
