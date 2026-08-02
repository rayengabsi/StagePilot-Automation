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

Phase 3 implements the Master Profile Engine for importing, normalizing, validating, persisting, versioning, managing, and exporting candidate profiles from resumes in **PDF, DOCX, and Markdown** formats.

See [`docs/phase-3-master-profile.md`](docs/phase-3-master-profile.md) for detailed documentation.

### Persistence (11 tables)

- `profiles` -- root aggregate with `active` flag (multi-profile support)
- `profile_versions` -- immutable JSON snapshots per import/edit
- `education` -- education history entries
- `experience` -- work experience entries
- `projects` -- project entries
- `skills` -- skill entries with category and proficiency
- `languages` -- language entries with proficiency
- `certifications` -- certification entries
- `awards` -- award/honor entries (NEW in Phase 7.6)
- `publications` -- publication/research entries (NEW in Phase 7.6)
- `preferences` -- one-to-one preferences (countries, cities, remote, technologies, etc.)

### Commands

```text
stagepilot profile import <file> [--description]   # PDF, DOCX, or Markdown
stagepilot profile show                              # PII-masked output
stagepilot profile export [--output]
stagepilot profile versions
stagepilot profile edit [--name] [--summary] [--profile-id]
stagepilot profile validate
stagepilot profile activate <id>
stagepilot profile list
stagepilot profile delete <id>
```

### PII Masking

`app/utils/pii.py` provides `mask_email()`, `mask_phone()`, `mask_url()`, and `mask_profile_dict()` for safe display. CLI `show` and `list` commands mask PII automatically. Stored data is never modified.

### Normalization Utilities

`app/utils/normalization.py` and `app/utils/text_cleaning.py` provide pure, deterministic helpers used by the parsers and the normalizer:

- `text_cleaning.clean()` — preprocesses raw extracted text (PDF `(cid:N)` artifacts, Unicode/ASCII bullets, broken line endings, NBSP/zero-width spaces, en/em dashes, control chars, collapsed blank lines).
- `normalization.canonical_technology()` — maps technology aliases to canonical names (e.g. `nodejs` → `Node.js`, `postgres` → `PostgreSQL`).
- `normalization.normalize_email()` / `normalize_url()` — canonical email and URL forms (scheme added, host lowercased, trailing slash stripped).
- `normalization.is_plausible_url()` — a known-TLD allowlist so tech suffixes like `Node.js` are never mistaken for bare URLs.
- `normalization.detect_degree()` — detects degree levels from full names and abbreviations (`B.S.`, `BSc`, `M.Sc.`, `MBA`, ...).
- `normalization.looks_like_role()` / `is_work_mode()` / `clean_company_name()` — classification and cleaning helpers.

The `PDFParser`, `DocxParser`, and `MarkdownParser` all run `text_cleaning.clean()` on extracted text before returning it, so the normalizer always receives consistent input.

### Extraction Quality Benchmark

Deterministic resume fixtures (ATS, modern tech, French Europass, academic, full-stack, contact-only) live in `tests/benchmark/fixtures.py` with per-fixture ground truth. `tests/benchmark/quality_report.py` runs the normalizer over every fixture and reports per-category and overall extraction accuracy:

```text
python -m tests.benchmark.quality_report
```

`tests/benchmark/test_benchmark.py` enforces the target thresholds (e.g. email/phone/LinkedIn/GitHub 100%, experience ≥ 98%, education ≥ 99%, overall ≥ 95%) so extraction regressions fail CI.


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

## Phase 5: AI Intelligence Layer

Phase 5 implements the AI Intelligence Layer — an optional, provider-abstracted AI subsystem that generates human-readable communication artifacts from structured recommendation and profile data.

**AI is advisory only.** It never makes hiring decisions, never changes scores, never overrides hard rules, and never modifies persisted recommendation data. All AI-generated content requires human review before use.

See [`docs/phase-5-ai-intelligence-layer.md`](docs/phase-5-ai-intelligence-layer.md) for detailed documentation.

### Architecture

```
+-------------------------------------------------------------------+
|                      AI Intelligence Layer                        |
+-------------------------------------------------------------------+
|                                                                   |
|  AIOrchestrator (single entry point)                              |
|  +---------------------------------------------------------+     |
|  |  1. PromptService.load(name) → render(vars)             |     |
|  |  2. AIProvider.generate(prompt) → AIResponse            |     |
|  |  3. OutputValidator.validate(text|json)                 |     |
|  |  4. TokenTracker.track(...) → persist                   |     |
|  +---------------------------------------------------------+     |
|              |                                                    |
|    +---------+---------+---------+---------+                     |
|    |         |         |         |         |                     |
|    v         v         v         v         v                     |
| Explain  Resume   Cover   Email   PromptService                   |
| Service   Tailor   Letter  Draft  (prompts/*.md)                 |
|           Service  Service Service                                |
|    |         |         |         |                                |
|    +---------+---------+---------+                                |
|              |                                                    |
|              v                                                    |
|    +-------------------+  +-------------------+                   |
|    |  GeminiProvider   |  |  AIProvider (ABC) |                   |
|    |  (google-genai)   |  |  (future)         |                   |
|    +-------------------+  +-------------------+                   |
|                                                                   |
+-------------------------------------------------------------------+

Inputs:
  +------------------+  +------------------+  +-------------------+
  |  Recommendation  |  |  MasterProfile   |  |  CoverLetter      |
  |  (Phase 4)       |  |  (Phase 3)       |  |  (domain entity)  |
  +------------------+  +------------------+  +-------------------+

Persistence:
  +------------------+
  |  ai_token_usage  |
  |  (Phase 5)       |
  +------------------+
```

### Provider Abstraction

- `AIProvider` (ABC) defines `generate(prompt, **kwargs) -> AIResponse`
- `GeminiProvider` implements the ABC using `google.genai.Client`
- Future providers (OpenAI, Claude, Ollama) require only: implementation file, enum entry, `_build_provider()` branch, config change
- No other code needs to change — orchestrator, validators, services, CLI, prompts are all provider-agnostic

### 4 Prompt Templates (versioned `.md` files)

| Prompt | Purpose |
|---|---|
| `match_explanation` | Generate human-readable explanation of score breakdown and matched/missing items |
| `resume_tailoring` | Tailor resume sections for a specific job (summary, skills, experience, projects) |
| `cover_letter` | Generate personalized cover letter body text |
| `email_application` | Draft full email (subject, body, signature) |

Each prompt file has front-matter metadata (`version`, `purpose`, `inputs`, `output`). All variable substitution uses `string.Template.safe_substitute()`.

### 4 AI Services

| Service | Method | Output Type | AI Call |
|---|---|---|---|
| `ExplanationService` | `explain(recommendation)` | `ExplanationResult` | `generate_text` |
| `ResumeTailorService` | `tailor(profile, recommendation)` | `TailoredResume` | `generate_json` |
| `CoverLetterService` | `generate(profile, recommendation)` | `CoverLetter` | `generate_text` |
| `EmailDraftService` | `draft(cover_letter)` | `EmailDraft` | `generate_json` |

### Deterministic Output Validation

- Empty/short rejection (< 10 chars)
- Prompt injection pattern detection (5 regex patterns)
- JSON parse validation + required field schema checks
- No ML, no heuristics, no second AI call

### Token Usage Tracking

Every AI API call is recorded in `ai_token_usage` (provider, model, feature, prompt version, token counts, latency, estimated cost). `TokenTracker` provides `track()` and `get_usage()` for analytics.

### CLI

```text
stagepilot ai explain <id> [--job-title] [--company]
stagepilot ai tailor-resume <id> [--job-description]
stagepilot ai cover-letter <id> [--company] [--recipient]
stagepilot ai email <id> [--company] [--job-title] [--recipient]
stagepilot ai usage [--limit N] [--feature F]
stagepilot ai prompts
```

### Design Constraints

- AI never modifies deterministic matching, filtering, or scoring results
- AI never sends emails or makes external calls beyond the configured LLM API

## Phase 6: Resume Rendering & Document Generation Engine

Phase 6 implements the document rendering engine — a deterministic, template-driven system that transforms structured profile data and AI-tailored content into professional PDF and DOCX documents. Python owns all layout, typography, pagination, and formatting.

See [`docs/phase-6-document-rendering.md`](docs/phase-6-document-rendering.md) for detailed documentation.

### Architecture

```
MasterProfile + AI Tailored Sections
                ↓
         RenderContext
                ↓
    ResumeRenderer / CoverLetterRenderer
                ↓
    ┌──────────────────┐
    │  RendererFactory  │
    └──────┬───────────┘
       ┌───┴───┐
       v       v
 PdfRenderer  DocxRenderer
 (reportlab)  (python-docx)
       │       │
       v       v
  resume.pdf  resume.docx
```

### Template System

- **5 data-driven templates** — modern, executive, minimal, classic, professional
- **Pure JSON** — each template is a `template.json` file under `templates/<name>/`
- **Zero code changes** to add a template — `TemplateLoader` auto-discovers

### Theme System

- Runtime overrides via `config/theme.toml`
- `ThemeDef.apply_to()` merges overrides with template, returns new `TemplateDef`
- Supports color, font, page size, margin, icon/photo visibility overrides

### PDF Rendering (reportlab)

- Selectable text via `Paragraph` with text operators
- ATS-compatible: standard fonts (Helvetica, Times-Roman), simple layout, extractable text
- Automatic page breaks via `SimpleDocTemplate` flowable overflow
- Consistent typography via `ParagraphStyle` per role

### DOCX Rendering (python-docx)

- Heading hierarchy: Heading 0 (name) → Heading 1 (sections)
- Professional formatting with consistent fonts, sizes, colors, margins
- Detailed section layout with dates and technologies

### CLI

```text
stagepilot render resume [--template] [--theme] [--format]
stagepilot render cover-letter [--template] [--theme] [--format]
stagepilot render templates
stagepilot render themes
stagepilot render preview [--template]
```

### Key Engineering Rules

- No AI in rendering pipeline — Python owns all document generation
- Templates are pure data (JSON), never code
- All config is immutable frozen dataclasses
- Renderers are provider-independent via `DocumentRenderer` ABC
- Adding a new template requires zero renderer or Python changes
- AI never persists data to tables outside `ai_token_usage`
- AI never makes business logic decisions
- AI never accesses the database directly
- All AI outputs must pass deterministic validation
- All AI calls must be tracked in `ai_token_usage`
- All prompts must be versioned `.md` files

## Phase 7 — Human Approval Platform

### Architecture

```
Application Package (snapshot + docs + hash)
        │
        v
   Approval Queue
        │
        v
  ApprovalService  ←── Telegram Bot (thin adapter)
        │                    Web UI (future)
        │                    Slack/Discord (future)
        v
  ┌──────────────┐
  │  State Machine  │
  │  8 states        │
  │  Validated       │
  │  transitions     │
  └──────────────┘
        │
        v
  ┌──────────────────────────────────────┐
  │  Database                            │
  │  ├ application_packages              │
  │  ├ approval_queue                    │
  │  ├ approval_events (audit log)       │
  │  └ approval_comments                 │
  └──────────────────────────────────────┘
```

### Key Design Decisions

- **ApprovalService owns ALL business logic** — Telegram, CLI, and future UIs are thin adapters
- **State machine** with 8 states and validated transitions — invalid transitions are impossible
- **Immutable snapshots** — every package entering the queue captures full state (recommendation, profile, documents, explanation, template, theme, hash)
- **Queue engine** supports 5 strategies: FIFO, highest score, deadline priority, newest first, oldest first
- **Audit log** records every action (queued, viewed, approved, rejected, skipped, revised, archived) with timestamp, actor, and comment
- **Telegram is a thin adapter** — zero business logic, only calls ApprovalService

### State Machine

```
NEW → QUEUED → UNDER_REVIEW → APPROVED → ARCHIVED
                              → REJECTED → QUEUED / ARCHIVED
                              → REVISION_REQUESTED → QUEUED / ARCHIVED
                    → SKIPPED → QUEUED / ARCHIVED
         → ARCHIVED
```

### Database Tables (4 new)

| Table | Purpose |
|-------|---------|
| `application_packages` | Full application state with immutable snapshot |
| `approval_queue` | Queue positioning (one-to-one with packages) |
| `approval_events` | Audit log |
| `approval_comments` | Reviewer comments |

### Telegram Commands

`/start`, `/help`, `/queue`, `/view`, `/open`, `/approve`, `/reject`, `/revise`, `/skip`, `/archive`, `/history`, `/status`

### CLI

```
stagepilot approval queue
stagepilot approval list
stagepilot approval approve <id>
stagepilot approval reject <id>
stagepilot approval revise <id>
stagepilot approval skip <id>
stagepilot approval archive <id>
stagepilot approval history <id>
stagepilot telegram run
```

## Phase 8 — Multi-Provider Job Discovery Platform

Phase 8 extends discovery from a single RSS reader into a multi-provider platform.
See [`docs/phase-8-provider-discovery.md`](docs/phase-8-provider-discovery.md) for
detailed documentation.

### Providers

Nine connector families join RSS/Atom, all extending the shared
`BaseJobSourceConnector`: Greenhouse, Lever, Ashby, SmartRecruiters, Teamtailor,
Welcome to the Jungle (WelcomeKit), RemoteOK, Wellfound, and configurable Company
Career Pages (CSS-selector based scraping with JSON-LD fallback).

### Shared Infrastructure

- `HttpClient` — pooled sessions, tenacity retries (429/5xx + transient errors),
  per-provider timeout/headers, `User-Agent` injection.
- `RateLimiter` — per-provider minimum interval between paginated requests.
- `app/infrastructure/html/parsing.py` — lxml/BeautifulSoup helpers for scraping.
- `app/config/providers.toml` + `ProvidersConfig` — per-provider HTTP/rate config.

### Registry

`build_connector_registry(settings)` auto-registers every enabled provider. The CLI
(`discover`) and `PipelineOrchestrator._run_discovery()` both use it, so new providers
are picked up automatically. `ConnectorRegistry.all()` exposes every registered
connector for validation/benchmarking.

### Provider Validation

`app/infrastructure/job_sources/validation.py` validates every connector against
mocked scenarios with no network access, measuring success rate, response time,
normalization quality, duplicate rate, and error handling against the canonical
`NORMALIZED_JOB_SCHEMA`. `SourceValidationService` aggregates the results into a
JSON-serializable `SourcesHealthReport` (see
[`docs/phase-8-provider-discovery.md`](docs/phase-8-provider-discovery.md)).

### Error Isolation

Discovery isolates failures per source: per-job failures skip the job and increment
the invalid counter, while per-source failures roll back and record a `failed`
metric before continuing with the next configured source. A provider outage never
interrupts discovery for other sources.

### Persistence

- `jobs` gains `department`, `employment_type`, `remote_status` columns.
- `discovery_metrics` records per-source metrics for every discovery run.
- Cross-provider duplicate merging by canonical URL keeps one canonical `jobs` row.

## Phase 9 — Job Intelligence Layer

Every normalized job is enriched with structured intelligence before recommendation
scoring: engineering specialization, seniority, employment type, work mode, and hiring
urgency. `JobClassificationService` derives these from configurable keyword
dictionaries in `app/config/classification.toml` (English + French variants) and
persists them in five nullable `classification_*` columns on `jobs` (migration
`20260802_p9`). Original extracted metadata is preserved unchanged.

The enrichment runs inside `DiscoveryService` immediately after normalization and is
provider-agnostic — new labels require only TOML changes. The classification fields
feed into `SimilarityScorer` and `HardRuleMatcher` so enriched labels improve
recommendation quality. See
[`docs/phase-8-provider-discovery.md`](docs/phase-8-provider-discovery.md) for the
full design.

### Commands

```text
stagepilot sources add-rss | add-greenhouse | add-lever | add-ashby |
           add-smartrecruiters | add-teamtailor | add-wttj | add-remoteok |
           add-wellfound | add-company
stagepilot sources list | remove | enable | disable | refresh | health | test | benchmark
```

## Phase 10 — Recommendation Intelligence Layer

The recommendation engine produces explainable, configurable, personalized output
without redesigning the Phase 4 pipeline. Every recommendation carries:

- **Weighted breakdown** — `WeightedBreakdown` records `final_score`, `total_weight`,
  and per-category `WeightedComponent`s (score, weight, weighted_score, contribution).
  `ScoreAggregator.aggregate_weighted()` builds it from the 13 configurable weights in
  `matching.toml` (`skills`, `technologies`, `education`, `experience`, `languages`,
  `projects`, `location`, `preferences`, `classification`, `remote`, `seniority`,
  `hard_filters`, `ai`); the scalar `aggregate()` is unchanged.
- **Confidence levels** — `ConfidenceCalculator` (`app/domain/recommendation/confidence.py`)
  assigns `VERY_HIGH`/`HIGH`/`MEDIUM`/`LOW` from quartiles of the run's score
  distribution, falling back to magnitude when scores are degenerate.
- **Deterministic reasoning** — `ReasoningBuilder` (`app/domain/recommendation/reasoning.py`)
  produces human-readable `reasons` and a `summary` from the breakdown and match detail
  (e.g. "Strong FastAPI and Python match", "Missing Docker experience",
  "Location mismatch"). No AI is required.

`Recommendation` extends with optional `weighted_breakdown` and `insights`; the
`RecommendationRecord` persists them as `weighted_breakdown_json` and `insights_json`
(migration `20260802_p10`). `RecommendationService` re-assigns confidence from the full
run distribution before persistence. Hard-rule-rejected recommendations receive the
same explanation surface. The `stagepilot recommend` table shows a Confidence column and
a `Why:` summary line; Telegram application messages include `*Confidence:*` and
`*Why:*`. A reserved `ai` weight slot (default 0.0) lets a future LLM contribution be
blended into the weighted breakdown via configuration alone. See
[`docs/phase-4-recommendation-engine.md`](docs/phase-4-recommendation-engine.md).

## Phase 11 — AI Tailoring Quality Layer

The AI Tailoring Quality Layer adds a deterministic quality gate on top of the Phase 5
AI orchestration without redesigning the provider abstraction or the prompts. `AIProvider`
interface, orchestrator, and prompt files are untouched — all checks are rule-based.

- **Quality report** — `AITailoringEvaluator` (`app/services/ai_tailoring_evaluator.py`)
  scores each generated document in six categories: `hallucination` (25), `keyword_coverage`
  (20), `factual_preservation` (20), `section_completeness` (15), `ats_keyword_density` (10),
  `grammar_format` (10). It detects invented skills/employers/degrees, missing job keywords,
  missing profile facts, empty sections, placeholders/control characters/terse prose, and ATS
  keyword density outside the ideal 0.03–0.08 band.
- **Structured output** — `QualityReport`/`QualityIssue` live in
  `app/domain/ai/quality.py` (`document_type`, per-category scores, overall score, quality
  level, `needs_revision`, issues). `TailoredResume` and `CoverLetter` carry an optional
  `quality` field; `None` when not evaluated (backward compatible).
- **Config** — `TailoringQualityConfig` (`enabled`, `minimum_quality_score = 60.0`) under the
  `[tailoring_quality]` section of `ai.toml`; a missing section defaults to enabled/60.0.
- **Pipeline gate** — `PipelineOrchestrator` persists both reports in the approval package
  snapshot under the `quality` key. Documents scoring below the threshold are **not** rendered
  or enqueued; instead a revision package is created with `status = REVISION_REQUESTED`,
  empty document paths, and the quality report attached (`ApprovalService.create_package`
  gained an optional `status` argument; `build_snapshot` gained an optional `quality`). The
  run result counts `needs_revision`. Disabling the gate bypasses evaluation entirely.
- **No AI self-evaluation** — evaluation is fully deterministic (regex, vocabulary, token
  counting), matching the Phase 5 "AI is advisory only" constraint: quality never changes
  scores or hard rules, it only routes low-quality output back for revision.
- **Tests** — 32 new tests (23 evaluator, 4 quality entities, 2 service quality attachment,
  3 pipeline integration) bring the suite to 620 passing with ruff clean. See
  [`docs/phase-5-ai-intelligence-layer.md`](docs/phase-5-ai-intelligence-layer.md).

## Phase 12 — Application Execution Engine

The Application Execution Engine starts after approval and tracks real job applications
independently from discovery, recommendation, tailoring, and approval. An approved
`ApplicationPackage` can be converted into a `JobApplication` while preserving traceability
to the recommendation, job, profile, profile version, rendered resume, cover letter, and
approval package.

```text
Recommendation -> AI Tailoring -> Rendering -> Approval Package -> Human Approval
                                                                       |
                                                                       v
                                                              ApplicationService
                                                                       |
                     +--------------------+----------------------------+----------------+
                     |                    |                                             |
              applications        application_events                         reminders/notes
                     |                    |                                             |
                     +-------------- timeline/outcomes/analytics -----------------------+
```

- **Lifecycle** — `ApplicationState` covers `draft`, `ready`, `submitted`, `viewed`,
  `interview`, `assessment`, `offer`, `rejected`, `withdrawn`, and `archived`. All
  transitions are explicit in `VALID_TRANSITIONS`; `archived` is terminal and reachable
  from active states for stale-record cleanup.
- **Auditability** — `application_events` stores lifecycle and metadata actions, while
  `application_timeline_events` provides a human-readable timeline.
- **Follow-ups** — `application_reminders` stores configurable reminders only; no external
  notification integration is introduced.
- **Outcomes and analytics** — `application_outcomes` records final outcomes. Analytics
  report submission counts, interview/offer/rejection rates, average response time, and
  pipeline conversion percentages.
- **CLI** — `stagepilot application` supports create/list/show/update/archive/search/
  summarize/analytics plus `application reminder` add/list/complete/snooze commands.
- **Persistence** — migration `20260802_p11` creates `applications`, `application_events`,
  `application_notes`, `application_timeline_events`, `application_reminders`, and
  `application_outcomes`.
- **Tests** — application domain, service, CLI, and integration coverage brings the suite
  to 696 passing with ruff clean. See
  [`docs/phase-12-application-execution-engine.md`](docs/phase-12-application-execution-engine.md).
