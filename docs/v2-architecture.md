# StagePilot v2 — AI Career Operating System (Architecture)

> **Status: Design — pending approval. No implementation has started.**
>
> This document is the complete architectural blueprint for StagePilot v2.
> v2 is NOT a job board, NOT a Telegram bot, and NOT an AI wrapper. It is an
> **autonomous AI career assistant** built as a reasoning engine where external
> services (LinkedIn, Exa, Jina, GitHub, Gmail, Calendar) are **capabilities the
> AI decides to use** — never integrations bolted onto the UI.

---

## 0. Positioning Decision

Before architecture, one product decision frames everything:

> **StagePilot is an AI Career Agent, not an internship finder.**

The career surface is a spectrum: internships → graduate programs → junior →
mid → senior roles → networking → recruiter outreach → interview prep → career
planning → skill-gap analysis. v2's architecture must not encode "internship"
anywhere. It encodes **career stage** as a first-class, evolving field.

Consequences of this decision:

- The job pipeline supports any seniority; seniority is a *filter*, not a type.
- The profile model captures **goals** (target roles, timelines, growth areas),
  not just facts.
- The strategy engine plans a **career path**, and each opportunity is evaluated
  against the current step in that path.
- The learning engine optimizes for *outcomes* (interview rate, offer rate),
  not just clicks.

---

## 1. High-Level Architecture

v2 is a **hexagonal, agent-first monolith** — one deployable, internally
layered into a reasoning core, a capability layer, and external world.

```text
                     ┌──────────────────────────────────────────────────┐
                     │                   CHANNELS                        │
                     │   FastAPI HTTP/WS  ·  Telegram  ·  CLI  ·  (Web)  │
                     └──────────────────────┬────────────────────────────┘
                                            │ requests / streams (SSE, WS)
                                            ▼
                     ┌──────────────────────────────────────────────────┐
                     │               AGENT CORE (reasoning)              │
                     │                                                    │
                     │   CareerAgent  (one orchestrator, two modes)      │
                     │   ├─ interactive  (user conversation)             │
                     │   └─ autonomous   (scheduled pipeline runs)       │
                     │          │                                        │
                     │          ▼                                        │
                     │      Planner  (intent → plan, mode, steps)        │
                     │          │                                        │
                     │          ▼                                        │
                     │     ToolRouter  (capability registry + guardrails)│
                     │          │                                        │
                     │          ▼                                        │
                     │    ExecutionContext (belief state, memory, cost)  │
                     └──────────┬────────────────────────────────────────┘
                                │ calls ports (interfaces) only
                                ▼
                     ┌──────────────────────────────────────────────────┐
                     │            APPLICATION LAYER (use cases)         │
                     │  profile · discovery · intelligence · matching    │
                     │  recommendation · strategy · cv · application     │
                     │  follow-up · approval · learning · analytics      │
                     │  (each depends on ports, never on adapters)       │
                     └──────────┬────────────────────────────────────────┘
                                │ ports
                                ▼
                     ┌──────────────────────────────────────────────────┐
                     │                  ADAPTERS                          │
                     │  ┌───────────┐ ┌───────────┐ ┌──────────────┐     │
                     │  │ MCP Manager│ │  LLM      │ │  DB/Redis   │     │
                     │  │ (LinkedIn, │ │ openai /  │ │ repositories │     │
                     │  │  gmail,    │ │ anthropic │ │ + cache      │     │
                     │  │  calendar) │ │ /gemini   │ │              │     │
                     │  └───────────┘ └───────────┘ └──────────────┘     │
                     │  ┌───────────┐ ┌───────────┐ ┌──────────────┐     │
                     │  │ Exa / Jina │ │ job source│ │ storage/     │     │
                     │  │ (search /  │ │ connectors│ │ notifications│     │
                     │  │  reader)   │ │ (v1 port) │ │              │     │
                     │  └───────────┘ └───────────┘ └──────────────┘     │
                     └──────────┬────────────────────────────────────────┘
                                │
                                ▼
                     ┌──────────────────────────────────────────────────┐
                     │                  EXTERNAL WORLD                    │
                     │  LinkedIn MCP · Gmail · Calendar · GitHub          │
                     │  Exa Search · Jina Reader · ATS (GH/Lever/…)       │
                     │  Company career pages · LLM APIs                   │
                     └────────────────────────────────────────────────────┘
```

### Invariant

> **The AI reasons first, chooses tools second, executes third, and explains
> its reasoning in human terms last.**
> Business logic never touches an external service directly; it speaks to
> ports. Adapters are the only place MCP/HTTP/SDK calls exist.

---

## 2. Folder Structure

```text
stagepilot/
├── app/
│   ├── main.py                      # FastAPI entrypoint + WS/SSE routes
│   ├── api/                         # HTTP layer (thin)
│   │   ├── deps.py                  # DI wiring (container → request)
│   │   ├── errors.py                # global exception → HTTP mapping
│   │   └── v1/
│   │       ├── agent.py             # POST /agent/chat, /agent/stream (SSE)
│   │       ├── auth.py              # login, API keys, sessions
│   │       ├── profiles.py          # CV upload, profile CRUD, versions
│   │       ├── jobs.py              # discovered jobs, search
│   │       ├── recommendations.py   # ranked, explainable results
│   │       ├── applications.py      # lifecycle, follow-ups
│   │       ├── approvals.py         # queue + decision endpoints
│   │       ├── analytics.py         # outcome dashboards
│   │       └── settings.py          # preferences, integrations, goals
│   ├── core/                        # Agent core (reasoning engine)
│   │   ├── agent.py                 # CareerAgent: orchestration loop
│   │   ├── agent_modes.py           # interactive vs autonomous
│   │   ├── planner.py               # intent → plan
│   │   ├── router.py                # ToolRouter + ToolRegistry
│   │   ├── guardrails.py            # risk tiers, approvals, safety
│   │   ├── context.py               # ExecutionContext (belief/memory state)
│   │   ├── composer.py              # human-friendly response builder
│   │   ├── learning.py              # LearningEngine (outcome A/B)
│   │   └── prompts/                 # agent-level prompts (versioned .md)
│   ├── domain/                      # Pure domain (no I/O)
│   │   ├── profile/                 # CareerProfile aggregate
│   │   ├── jobs/                    # Job, JobIntelligence
│   │   ├── matching/                # MatchResult, ScoreBreakdown
│   │   ├── recommendation/          # Recommendation, RankedItem
│   │   ├── strategy/                # CareerPlan, OpportunityAnalysis
│   │   ├── application/             # Application, FollowUp, Outcome
│   │   ├── approval/                # ApprovalPackage, state machine
│   │   ├── learning/                # Experiment, CVVariant
│   │   └── shared/                  # value objects, errors, enums
│   ├── application/                 # Use-case services
│   │   ├── profile_service.py
│   │   ├── discovery_service.py
│   │   ├── job_intelligence_service.py
│   │   ├── matching_service.py
│   │   ├── recommendation_service.py
│   │   ├── career_strategy_service.py
│   │   ├── cv_service.py            # tailoring + quality + rendering
│   │   ├── application_service.py
│   │   ├── followup_service.py
│   │   ├── approval_service.py
│   │   ├── learning_service.py
│   │   ├── analytics_service.py
│   │   ├── notification_service.py
│   │   └── scheduler_service.py
│   ├── ports/                       # Hexagonal interfaces (ABCs only)
│   │   ├── capability.py            # CapabilityPort (adapter contract)
│   │   ├── llm.py                   # LLMPort
│   │   ├── search.py                # SearchPort (Exa + future)
│   │   ├── reader.py                # PageReaderPort (Jina + future)
│   │   ├── jobs_provider.py         # JobsProviderPort (ATS connectors)
│   │   ├── social.py                # LinkedIn/social actions
│   │   ├── email.py                 # EmailPort
│   │   ├── calendar.py              # CalendarPort
│   │   ├── cache.py                 # CachePort
│   │   ├── storage.py               # object/file storage
│   │   ├── notifications.py
│   │   └── repositories.py          # persistence ports per aggregate
│   ├── adapters/                    # Implementations (the only I/O)
│   │   ├── mcp/
│   │   │   ├── manager.py           # McpClientManager (lifecycle, auth)
│   │   │   ├── base.py              # McpToolAdapter base class
│   │   │   └── config.py            # per-server config loading
│   │   ├── linkedin/                # LinkedIn MCP adapter → CapabilityPort
│   │   ├── exa/                     # Exa HTTP adapter → SearchPort
│   │   ├── jina/                    # Jina Reader adapter → PageReaderPort
│   │   ├── github/
│   │   ├── gmail/                   # Gmail MCP adapter → EmailPort
│   │   ├── calendar/                # Calendar MCP adapter → CalendarPort
│   │   ├── llm/                     # OpenAI / Anthropic / Gemini
│   │   ├── job_sources/             # v1 connectors ported (RSS, GH, Lever…)
│   │   ├── cache/                   # Redis / in-memory
│   │   ├── storage/
│   │   ├── telegram/                # Telegram channel adapter
│   │   └── notifications/
│   ├── infrastructure/              # cross-cutting concerns
│   │   ├── db/                      # SQLAlchemy models + repositories
│   │   ├── http/                    # pooled client, retry, rate-limit
│   │   ├── auth/                    # JWT, API keys, scopes
│   │   ├── logging.py               # structured JSON + redaction
│   │   ├── telemetry.py             # traces, metrics, token usage
│   │   ├── errors.py                # typed error taxonomy
│   │   └── outbox.py                # transactional outbox
│   ├── schemas/                     # Pydantic request/response models
│   ├── workers/                     # background jobs
│   │   ├── discovery_worker.py      # autonomous discovery runs
│   │   ├── followup_worker.py       # reminder + follow-up generation
│   │   ├── learning_worker.py       # outcome attribution + A/B evaluation
│   │   └── scheduler.py             # cron/tick orchestration
│   └── config/                      # Settings (Pydantic) + TOML files
├── migrations/                      # Alembic
├── prompts/                         # versioned prompt templates (domain-level)
├── docs/
├── tests/
│   ├── unit/  ├── integration/  ├── adapters/  ├── agent/  └── e2e/
└── pyproject.toml
```

---

## 3. Responsibilities of Every Folder

| Folder | Responsibility |
|---|---|
| `api/` | Thin HTTP/WS/SSE boundary. Auth, serialization, error mapping. Zero business logic. |
| `core/` | The **reasoning engine**: agent loop, planning, tool routing, guardrails, response composition, learning. Depends on `application/` + `ports/` only. |
| `domain/` | Pure business entities and rules (models, enums, validations, state machines). No I/O, no LLM, no MCP. |
| `application/` | Use-case orchestration. One class = one responsibility. Depends on `domain/` + `ports/`. |
| `ports/` | Interface contracts (ABCs) that isolate business logic from the world. |
| `adapters/` | Implementations of ports. The **only** place MCP servers, HTTP SDKs, and file I/O are touched. |
| `infrastructure/` | Cross-cutting plumbing: DB session/repositories, HTTP client, auth, logging, telemetry, outbox. |
| `workers/` | Scheduled/background entry points that drive autonomous agent modes. |
| `schemas/` | Wire DTOs (Pydantic) for the API and channels. |
| `config/` | Environment settings + tuned TOML (weights, risk tiers, providers, prompts). |

---

## 4. Responsibilities of Every Key Class

### Core (agent)

| Class | Responsibility |
|---|---|
| `CareerAgent` | Entry orchestrator. Receives messages (interactive) or ticks (autonomous). Runs the loop: context → plan → route → execute → reason → compose → persist. |
| `Planner` | Decomposes intent into a plan (ordered steps, target capabilities, mode). Uses LLM for open-ended intents, deterministic rules for known flows. |
| `ToolRegistry` | Catalog of every available tool: `{name, description, schema, capability, risk_tier, cost, requires_approval}`. |
| `ToolRouter` | Selects a tool per plan step. LLM function-calling for discovery; deterministic override for high-risk or forbidden operations. |
| `Guardrails` | Enforces risk tiers: read-only auto-allowed; write-scoped auto-allowed; **high-risk (email, apply, CV mutation) → routed to ApprovalService and halted**. Validates external content before it reaches the model or is executed (injection defense). |
| `ExecutionContext` | Holds the current run's belief state: profile snapshot, memory, tool results, running cost, correlation id. |
| `Composer` | Turns raw results + reasoning into a human-friendly answer: narrative + structured evidence + next-step suggestions. |
| `LearningEngine` | Attributes outcomes (interview/offer/reject) to CV variants and agent decisions; proposes better variants; persists experiments. |

### Application layer (one responsibility each)

| Service | Responsibility |
|---|---|
| `ProfileService` | CV import → parse → normalize → validate → `CareerProfile` persist + versioning. |
| `DiscoveryService` | Multi-source gathering orchestration (LinkedIn MCP, ATS connectors, company pages, web search) → merge → dedup → normalize. |
| `JobIntelligenceService` | Extract per-job intelligence (salary, visa, remote policy, deadline, recruiter, hiring manager, benefits). |
| `MatchingService` | Deterministic + AI-assisted explainable scoring; produces `MatchResult`. |
| `RecommendationService` | Rank matches, compute confidence, persist ranked recommendations. |
| `CareerStrategyService` | Overlays career insight on each opportunity (fit, interview chance, growth, reputation, competition, missing skills). |
| `CvService` | Decides whether to tailor, generates tailored CV / cover letter / recruiter message / LinkedIn request, runs quality gate, renders. |
| `ApplicationService` | Converts an approved package into a tracked application; owns lifecycle transitions. |
| `FollowUpService` | Schedules reminders, detects stalls, drafts follow-up content for approval. |
| `ApprovalService` | Owns ALL approval business logic; state machine; immutable snapshots; audit. |
| `LearningService` | Persists variants/experiments; computes outcome rates per variant. |
| `AnalyticsService` | Aggregates funnel metrics, interview/offer rates, response times. |
| `NotificationService` | Multi-channel delivery (Telegram, push, email digest) — never business logic. |
| `SchedulerService` | Cron/interval registration for autonomous modes. |

### Ports (contracts)

| Port | Contract |
|---|---|
| `CapabilityPort` | Generic capability: `list_tools()`, `call_tool(name, args)`, `health()`. Base for MCP-backed capabilities. |
| `SearchPort` | `search(query, filters) → SearchResults` (Exa and future engines). |
| `PageReaderPort` | `read(url) → PageContent` (Jina Reader and future). |
| `JobsProviderPort` | `fetch(scope) → DiscoveredJob[]` (ATS connectors). |
| `SocialPort` | LinkedIn actions: profile lookup, job search, connection request, recruiter message (LinkedIn MCP adapter). |
| `EmailPort` | `send(composed_email)` + `fetch_threads()` (Gmail MCP adapter). |
| `CalendarPort` | `list_events()`, `create_event()` (Calendar MCP adapter). |
| `LLMPort` | `generate(prompt, schema?)`, `complete_tool_call()`, token metadata. |
| `CachePort` | `get/set/delete` with TTL; keyspaces per data class. |
| `Repositories` | Persistence ports per aggregate (profile, job, match, rec, application, approval, experiment, memory, audit). |

### Adapters

| Adapter | Responsibility |
|---|---|
| `McpClientManager` | Owns MCP server connections (stdio/SSE/HTTP), auth, lifecycle, retries, timeouts, tool discovery. Exposes tool calls to capability adapters. |
| `McpToolAdapter` | Base class mapping a domain port method → one or more MCP tool calls; normalizes MCP JSON-RPC responses into domain objects. |
| `LinkedInAdapter` | Implements `SocialPort` + `JobsProviderPort` via LinkedIn MCP. |
| `GmailAdapter` / `CalendarAdapter` | Implement `EmailPort` / `CalendarPort` via their MCP servers. |
| `ExaAdapter` | Implements `SearchPort` via HTTP SDK. |
| `JinaAdapter` | Implements `PageReaderPort` via `r.jina.ai` / SDK. |
| `LLMAdapters` | OpenAI / Anthropic / Gemini behind `LLMPort`. |
| `JobSourceAdapters` | Ported v1 connectors (RSS, Greenhouse, Lever, Ashby, SmartRecruiters, Teamtailor, WTTJ, RemoteOK, Wellfound, company pages) behind `JobsProviderPort`. |

---

## 5. Service Communication

- **Direct, synchronous, typed calls** between `application/` services through ports (service A depends on port, container injects service B implementation). No implicit global state.
- **Agent ↔ services:** the `CareerAgent` may only call `application/` services and ports, never adapters.
- **Decoupling via events:** domain events (`job_discovered`, `application_submitted`, `outcome_recorded`, `variant_served`) are emitted on an in-process event bus. Workers and cross-cutting concerns (analytics, learning, notifications) subscribe. This prevents cycles and keeps learning/analytics additive.
- **Async boundary:** HTTP handlers and the agent loop are `async`. CPU-heavy work (PDF parsing, vector similarity, rendering) is delegated to a thread/process executor. Background work goes through a job queue (Redis-based) consumed by `workers/`.
- **Transactional outbox:** events that must not be lost (application submitted, approval granted, email sent) are written in the same DB transaction as the state change and published reliably by the outbox relay.
- **No shared mutable state:** `ExecutionContext` is per-run and injected; repositories are per-request.

```text
CareerAgent ──► application services ──► ports ──► adapters
     │                 │                      │
     └─events──────────┴──(outbox)──► analytics · learning · notifications
```

---

## 6. Sequence Diagrams

### 6a. Interactive conversation (user asks "find me cloud internships in Germany")

```text
User ──► CareerAgent.on_message()
  1    ContextAssembly: load CareerProfile + memory + pending approvals
  2    Planner: intent = discovery; mode = interactive; plan = [search, evaluate, rank, report]
  3    Router: choose "search_jobs" tool (LinkedIn MCP) + "web_search" (Exa) fallback
  4    Guard: tier = read → allowed
  5    LinkedInAdapter.call_tool("search_jobs", {...}) ──► LinkedIn MCP ──► results
  6    ExaAdapter.search(...) ──► semantic web results
  7    Merge → dedup (repository) → normalize → persist jobs
  8    MatchingService.match(profile, jobs) → MatchResult[]
  9    RecommendationService.rank(...) → ranked, persisted
 10    CareerStrategyService.analyze(...) → per-opportunity insight
 11    Composer: narrative + ranked table + "want me to tailor a CV for #1?"
 12    Persist conversation + events + token usage; emit job_discovered
```

### 6b. Autonomous discovery run (scheduled)

```text
Scheduler ──► DiscoveryWorker ──► CareerAgent.run_autonomous("discovery")
  1    ContextAssembly (profile snapshot, last-run cursor, config)
  2    Planner: plan = [multi-source discovery, dedup, intelligence, match, rank, summarize]
  3    Router: loop over sources (LinkedIn MCP, ATS connectors, company pages, Exa)
  4    Per source: fetch → normalize → dedup → persist (per-source failure isolation)
  5    JobIntelligenceService.enrich(each job)
  6    MatchingService + RecommendationService + CareerStrategyService
  7    Composer: daily digest (N new, M matches ≥ threshold)
  8    NotificationService.send(digest); persist run metrics + events
```

### 6c. Application with human approval (the only high-risk path)

```text
User taps "apply to #1"
  1    CareerAgent → Planner: intent = apply; plan = [assess, tailor, draft, approve, send, track]
  2    CvService: decide tailor? → generate tailored CV + cover letter + recruiter msg + LinkedIn req
  3    QualityGate (deterministic) → needs_revision? loop back to CvService
  4    Rendering → artifacts
  5    ApprovalService.create_package(snapshot incl. all 4 artifacts, hash, audit)
  6    NotificationService → "Approve? Review package" (Telegram/UI)
  7    User approves → ApprovalService.transition(APPROVED)
  8    ApplicationService.convert_to_application(package) → state=submitted
  9    EmailPort.send (Gmail MCP) + SocialPort LinkedIn actions
 10    FollowUpService.schedule(reminder); LearningEngine.record(variant_served)
```

---

## 7. Data Flow (end to end)

```text
CV (PDF/DOCX/MD) ──► parse ──► normalize ──► validate
      │
      ▼
CareerProfile (persisted, versioned)
      │  + answers to follow-up questions (goals, countries, visa, salary…)
      ▼
Career Strategy (plan: targets, seniority band, gap list)
      │
      ▼
Discovery: LinkedIn MCP ─┐
          ATS connectors ─┼─► merge ─► dedup ─► normalize ─► jobs
          company pages  ─┤
          Exa search     ─┘
      │
      ▼
Job Intelligence (salary, visa, remote, deadline, recruiter)
      │
      ▼
Match (explainable) ─► Rank + Confidence ─► Strategy overlay
      │
      ▼
Ranked recommendations (persisted)
      │
      ▼  user selects
Tailored CV + cover letter + recruiter msg + LinkedIn request
      │
      ▼  quality gate
Render ─► ApprovalPackage ─► human approve
      │
      ▼
Application (persisted) ─► Follow-ups (reminders) ─► Outcome
      │
      └────────────► LearningEngine (variant → outcome attribution)
      └────────────► AnalyticsService (funnel)
```

---

## 8. MCP Integration Strategy

**Rule:** MCP servers are capabilities, reached only through the capability
layer. No business logic and no agent code ever imports an MCP client directly.

```text
application service ─► port (e.g. SocialPort.search_jobs)
                          │
                          ▼
                adapter (LinkedInAdapter)
                          │  domain command → MCP tool mapping
                          ▼
              McpClientManager ─► MCP server (stdio/SSE/HTTP)
                          │  JSON-RPC, auth, retries, health
                          ▼
                  External (linkedin.com)
```

- **One MCP server per adapter.** A new server = `adapters/<name>/` + an
  entry in `adapters/mcp/config.py` + (if a new domain action) a port method.
  Existing business logic is untouched — this is the modularity contract.
- **`McpClientManager`** owns connection lifecycle: stdio for local servers,
  SSE/HTTP for remote, per-server auth (API key / OAuth token vault), timeouts,
  retries, circuit breaker, and periodic `health()` probes.
- **Tool discovery** surfaces each MCP server's tool list into `ToolRegistry`
  as agent-visible tools with `description` + JSON schema, so the AI can reason
  about when to use them.
- **Response normalization:** adapters convert raw JSON-RPC tool results into
  domain objects (`DiscoveredJob`, `Contact`, `EmailDraft`, …) before anything
  else sees them. External schema never leaks past the adapter.
- **Dev-time tooling:** MCP Inspector is the canonical way to inspect and
  debug server tool schemas during adapter development. Documented in the
  developer guide; it is not part of the runtime.
- **Failure semantics:** per-capability. LinkedIn down → discovery falls back
  to Exa/Jina/ATS connectors; the run degrades, never fails wholesale.

---

## 9. AI Reasoning Flow

```text
1  ASSEMBLE   context: CareerProfile · memory (conversation, decisions, outcomes)
              · pending approvals · config · run budget
2  PLAN       LLM proposes intents & steps (or deterministic known-flow planner)
              constrained by an explicit capability schema
3  ROUTE      for each step: ToolRouter picks tool from ToolRegistry
              (LLM function-call + guardrail overlay for risk/allowlist)
4  GUARD      risk tier: READ → run; WRITE-SCOPED → run + log;
              HIGH-RISK → approval gate, halt
5  EXECUTE    adapter call; observation normalized into domain object
6  REASON     update ExecutionContext; decide loop / next step / finish
              (budget & max-steps guard rails prevent runaway loops)
7  COMPOSE    human-friendly answer: what I did, why, evidence, next steps
8  PERSIST    memory, domain events, token usage, audit trail
```

Guard rails that bound the AI at all times:

- Deterministic rules (hard filters, duplicate detection, PII, state machines,
  quality gate) are **authoritative** and cannot be overridden by the model.
- High-risk actions are structurally impossible without a human approval event.
- External page/result content is validated before being passed to the model
  or executed (prompt-injection defense at the adapter boundary).
- Every autonomous run is bounded (time, steps, cost, number of external calls).

---

## 10. Career Profile Model

```text
CareerProfile (aggregate root)
├── id, version, active, created/updated
├── personal: full_name, email, phone, location, nationality, linkedin, github,
│             portfolio, summary, photo_ref
├── skills:        [Skill{name, category, proficiency, years}]
├── technologies:  [Tech{name, category: language/framework/cloud/db/tool}]
├── soft_skills:   [string]
├── languages:     [Language{name, proficiency}]
├── education:     [Education{degree, field, school, start, end, gpa, notes}]
├── certifications:[Certification{name, issuer, year, url}]
├── experience:    [Experience{company, title, start, end, current, bullets,
│                   technologies, highlights}]
├── projects:      [Project{name, description, technologies, url, outcomes}]
├── publications / awards
├── preferences:   preferred_countries, preferred_cities, remote_pref,
│                  employment_types (internship|full-time|graduate|…),
│                  salary_min, salary_currency, visa_sponsorship_required,
│                  preferred_technologies, work_mode
├── goals:         target_roles[], career_stage, target_timeline,
│                  growth_areas[], dealbreakers[]
└── answers:       {question_id: answer}   # answers to follow-up questions
```

Model rules:

- **Career stage is explicit** (`career_stage`) and drives filtering weights.
- Goals and preferences are first-class, not appended to resume text.
- Versioned immutably; every edit creates a new version (v1 pattern reused).
- PII is encrypted at rest and masked in all output surfaces.

---

## 11. Job Model

```text
Job
├── id, canonical_url, source, source_id, external_id
├── title, company, department
├── location, remote_status, employment_type, seniority
├── work_mode, engineering_specialization, hiring_urgency   # classification
├── salary_min, salary_max, salary_currency, salary_period
├── description_raw, description_clean
├── requirements[]            # extracted must-have
├── preferred_skills[]        # extracted nice-to-have
├── benefits[]
├── visa_support, remote_policy, application_deadline
├── recruiter{name, linkedin, email}, hiring_manager{name, title}
├── company_website, careers_page, posted_at, scraped_at
├── hashes: raw_hash, normalized_hash, canonical_hash
├── raw_payload_json           # source-specific, immutable
└── status: new | matched | recommended | applied | closed | ignored
```

**Job Intelligence** (`JobIntelligenceService`) produces the structured fields
above from raw descriptions using a hybrid of deterministic extraction
(regex/JSON-LD) + LLM extraction with schema validation, always preserving
the original text for audit.

---

## 12. Matching Model

```text
MatchResult
├── job_id, profile_id, profile_version
├── eligible: bool                      # hard-rule gate (authoritative)
├── rejection: [{category, detail, matched_keyword}]   # if not eligible
├── final_score: float 0–100
├── confidence: VERY_HIGH|HIGH|MEDIUM|LOW
├── categories: [{category, score, weight, contribution}]   # breakdown
├── matched:   [{item, reason}]
├── missing:   [{item, reason, importance}]
├── reasoning: {summary, bullet_points[]}   # human-readable, deterministic base
└── ai_blend:  {score, rationale, weight}   # optional LLM contribution slot
```

Rules:

- Percentages are never returned alone. Every score ships with **matched /
  missing / reasons** — the explainable contract.
- Hard rules cannot be overridden; the AI may add context, never change the gate.
- Deterministic reasoning is the baseline; AI refines wording, not truth.

---

## 13. Recommendation Model

```text
Recommendation
├── id, job, match_result (nested), profile, profile_version
├── rank_position, overall_score, confidence
├── strategy:  OpportunityAnalysis
│   ├── company_fit, expected_interview_chance, career_growth
│   ├── market_reputation, estimated_competition
│   ├── missing_skills[] with learnability, recommended_next_steps
│   └── rationale: narrative why-this-company-fits
├── status: pending | shortlisted | applied | dismissed | archived
└── feedback: [{reason, comment}]       # user feedback feeds learning
```

The strategy overlay is what separates "here are jobs" from "here is why these
fit you and what to do next."

---

## 14. Application Model

```text
Application
├── id, recommendation_id, job_id, profile_id, approval_package_id
├── state: submitted | viewed | interview | technical_test | hr_interview
│          | offer | rejected | withdrawn | waiting | archived   (state machine)
├── artifacts_refs: tailored_cv, cover_letter, recruiter_msg, linkedin_request
├── cv_variant_id                       # which variant was used (learning)
├── submitted_at, last_activity_at
├── events[]: timestamp, from, to, actor, note        # audit timeline
├── reminders: [FollowUp{type, due_at, status, draft_ref}]
└── outcome: {type, at, notes, compensation} | null
```

Transitions are explicit (`VALID_TRANSITIONS`), `archived` is terminal.

---

## 15. Database Schema

Tables grouped by aggregate. (All rows carry `created_at`; sensitive columns
are encrypted.)

```text
-- Profile
profiles, profile_versions, education, experience, projects, skills,
technologies, soft_skills, languages, certifications, awards, publications,
preferences, career_goals, profile_answers

-- Jobs & discovery
job_sources, raw_jobs, jobs, job_intelligence, discovery_runs,
discovery_metrics, job_salaries

-- Matching & recommendation
job_matches, score_breakdowns, recommendations, recommendation_feedback,
opportunity_analyses, matching_runs

-- Applications
applications, application_events, application_timeline_events,
application_reminders, application_outcomes

-- Approval
approval_packages, approval_queue, approval_events, approval_comments

-- CV / learning
cv_variants, cv_quality_reports, experiments, experiment_variants,
outcome_attributions

-- Agent & memory
conversations, conversation_messages, agent_runs, tool_calls, memory_entries

-- MCP / integrations
capabilities, mcp_servers, capability_health

-- Cross-cutting
users, api_keys, sessions, notifications, outbox, ai_token_usage, audit_events
```

Key indexes: `jobs.canonical_url UNIQUE`, `jobs.(source_id, external_id) UNIQUE`,
`job_matches.job_id UNIQUE`, `applications.(recommendation_id)`,
`recommendations.(profile_id, status)`, `outbox.(id, published_at)`.

---

## 16. Caching Strategy

- **Never cache:** profile facts, approval state, application state, decisions,
  audit rows. These are source of truth in the DB.
- **Cache volatile external data** (cache-aside, via `CachePort`, Redis):
  - Job listings from MCP/ATS sources — TTL 15–60 min, keyed by source+cursor.
  - Web page content (Jina) — TTL 24 h, keyed by URL hash.
  - Exa search results — TTL 60 min, keyed by query hash + filters.
  - LinkedIn profile snapshots — TTL 12 h (respect ToS/rate limits).
  - LLM completions for deterministic prompts — TTL keyed by prompt+input hash
    (never for dynamic agent reasoning).
- **Embeddings cache** for job descriptions and profile (for semantic matching
  improvements); invalidated on job/profile change.
- **Rate-limit & circuit state** in Redis (shared across replicas).
- **Distributed lock** (Redis) so autonomous discovery runs never overlap.
- Freshness metadata on every cached object (`cached_at`, `source_generation`)
  so staleness is visible and steerable.

---

## 17. Error Handling

- **Typed taxonomy:** `DomainError` (invariants), `UseCaseError` (business
  rules, e.g. approval required), `PortError` (transient: timeout/rate-limit/
  outage) vs `PermanentError` (bad config, auth failure, 4xx schema change).
- **Retry policy** (tenacity): transient errors retried with backoff + jitter
  per capability; configurable per adapter.
- **Circuit breaker** per capability (`/health` probes + failure counters):
  open circuit → skip/fallback, log, notify.
- **Degradation:** a failed source never aborts a run (v1 pattern preserved).
  LinkedIn down → Exa/Jina/ATS fallback; discovery continues.
- **Compensation:** multi-step flows (tailor → render → approve → send) are
  idempotent at each step; a failed step leaves a recoverable state, and the
  outbox guarantees exactly-once effect for sends.
- **Surface to user:** human-readable error + what the agent did about it
  ("LinkedIn was unreachable; I found 12 matches on company websites instead").
- **Observability hook:** every retry/fallback/compensation emits an event.

---

## 18. Logging

- **Structured JSON**, one event per line, with `correlation_id` (per agent run
  / HTTP request) and optional `span_id` for trace grouping.
- **Event catalog** (stable names): `agent_run_started`, `tool_invoked`,
  `tool_failed`, `job_discovered`, `job_duplicate_skipped`, `match_computed`,
  `approval_requested`, `application_submitted`, `followup_scheduled`,
  `outcome_recorded`, `variant_served`, `circuit_opened`, `fallback_used`.
- **Redaction by default:** PII fields (email, phone, profile text) and secrets
  are redacted at the formatter level; developers opt-in to see masked values.
- **Audit trail** persists approval and application decisions to the DB (not
  just logs) for immutable history.
- **Telemetry:** per-tool latency and cost, LLM token usage, capability health,
  discovery metrics — exported to a metrics store for dashboards.

---

## 19. Security

| Concern | Design |
|---|---|
| AuthN | Email+password / magic link / OAuth (Google) with JWT short-lived access + refresh tokens; Telegram auth via existing trusted flow. |
| AuthZ | Per-user scopes; agent tools carry `risk_tier`; high-risk tools require `approval` scope event, not just a token. |
| Secrets | `.env`/secret manager; never in code/DB; MCP auth stored encrypted (key vault). |
| PII | Encrypted at rest (column-level); masked in logs, UI, CLI, and API responses. |
| Injection defense | External content validated at the adapter boundary before reaching the model or executing a tool; LLM outputs schema-validated (v1 pattern). |
| Prompt-injection | Agent treats all external text as data; tools that mutate/execute are gated by risk tier. |
| Human gate | Emails and external applications are structurally impossible without an approval event. |
| Rate limiting | Per-user and per-capability limits (Redis token bucket). |
| Network | All external calls via outbound allowlist; MCP servers pinned to trusted endpoints. |
| Audit | Every high-risk and approval action is an immutable `audit_events` row. |

---

## 20. Testing Strategy

| Layer | Approach |
|---|---|
| Domain unit tests | Pure logic: models, state machines, matching/scoring, dedup, validation (port v1's 696 tests where relevant). |
| Adapter tests | Mock MCP servers / HTTP mocks; golden fixtures for tool schemas; assert domain mapping correctness. Use MCP Inspector manually for live server schema verification. |
| Application tests | Use-case tests with in-memory repositories + fake ports; verify orchestration and compensation paths. |
| Agent tests | Simulated `ToolRegistry`; assert planning → routing → guardrail → composition for golden conversations; assert high-risk halts. |
| Integration tests | Real DB (test schema), real Redis, fake external world; full pipeline runs (v1 pattern). |
| E2E | One happy path (upload CV → discover → match → recommend → tailor → approve → apply → follow-up) against sandboxed external services. |
| Quality gates | Ruff + mypy + pytest in CI; deterministic extraction benchmark (v1 `quality_report`) retained; AI output quality gate tested. |
| Property/fuzz | Duplicate detection, normalization, state-machine transition invariants. |
| Cost guardrails | Tests asserting autonomous runs respect step/cost budgets. |

---

## 21. Scalability Strategy

- **Async everywhere** (FastAPI + async adapters); CPU-bound work offloaded to
  executors; DB/Redis connections pooled.
- **Stateless API:** all state in DB/Redis → horizontal scale-out of the API
  layer. Agent runs are sharded by user with a sticky execution key where needed.
- **Background work scaled separately:** `workers/` scale independently,
  consumed from a Redis queue; each autonomous run is a job.
- **Outbox → reliable events:** exactly-once semantics for sends and analytics,
  so the system tolerates worker restarts.
- **Caching layer** absorbs external-source variance (LinkedIn/Exa rate limits).
- **Multi-user ready:** every table carries `user_id` (or `tenant_id`) from day
  one, even though v2 ships single-user. Future SaaS = filter + auth, no schema
  redesign.
- **Performance budget:** discovery run must not exceed a bounded number of
  external calls; matching runs are bulk-efficient (single profile, batched jobs).

---

## 22. Future Extension Strategy

| Extension | How the architecture absorbs it |
|---|---|
| New MCP server | Add `adapters/<name>/` + config entry. Business logic unchanged. |
| New search engine | Implement `SearchPort`. Nothing else changes. |
| New LLM provider | Implement `LLMPort`. |
| New channel (Slack/Web/desktop) | Add a thin adapter → same agent API. |
| SaaS / multi-tenant | `tenant_id` already modeled; auth + isolation only. |
| New domain capability (e.g. interview simulator, salary analytics) | New domain context + service; agent gains a tool in the registry. |
| Plugin/marketplace | `ToolRegistry` + capability descriptors become the plugin contract. |
| On-device/local MCP servers | `McpClientManager` already abstracts stdio transport. |
| Vector semantic matching | Embeddings cached; swap `MatchingService` internals behind the same port. |

---

## 23. Relationship to v1 (migration)

v1 is a **deterministic-first** modular monolith (Phases 0–12) whose
principles remain non-negotiable in v2:

- Deterministic hard filters, duplicate detection, state machines, PII safety,
  and quality gates are **authoritative**.
- AI is advisory for facts, and every high-risk external action requires human
  approval.

Migration strategy (after this design is approved):

1. Adopt the v2 package layout; move existing `domain/`, `services/`, and
   `infrastructure/` code into the new boundaries **unchanged in behavior**
   (the deterministic core becomes `domain/` + `application/` under v2 rules).
2. Add `ports/` over existing infrastructure (job sources, parsers, LLM,
   storage) so the agent core can depend on contracts only.
3. Introduce `core/` (agent, planner, router, guardrails) as a new layer on
   top; Telegram becomes an adapter behind the same agent API.
4. Add the FastAPI + Redis + workers + outbox substrate.
5. Wire MCP capabilities behind the new adapters one at a time, starting with
   LinkedIn, Exa, and Jina.
6. Delete dead v1-specific entry points only after parity is demonstrated.

---

## 24. Open Decisions (for approval)

1. **Coexistence:** run v2 alongside v1 (new package) vs. in-place migration of
   the existing `app/`. Recommended: in-place, phase-by-phase, so v1 value is
   never lost.
2. **LLM default:** keep Gemini (current), or default to OpenAI with
   Anthropic/Gemini available? Recommended: `LLMPort` with OpenAI default and
   Gemini retained.
3. **DB:** keep MySQL (current) or move to PostgreSQL for JSON/vector support?
   Recommended: keep MySQL for v2.0; the port abstraction keeps the option open.
4. **Embeddings:** enable semantic matching in v2.0 or defer to a follow-up?
   Recommended: defer; deterministic matching ships first, embeddings plug into
   the same port.
5. **Agent autonomy ceiling:** user confirms every high-risk action (email,
   apply, CV mutation) is always gated by approval — never a one-time "auto-run"
   toggle. Recommended: yes, always gated.

---

## 25. Suggested Implementation Order (after approval)

1. Substrate: v2 layout, ports, container/DI, FastAPI, Redis, workers, outbox,
   logging/telemetry, typed errors.
2. `core/` skeleton: agent loop, planner, router, guardrails, composer, memory
   — with an in-memory `ToolRegistry` and no external tools.
3. Port the deterministic engine (profile, discovery, dedup, matching,
   recommendation) behind ports.
4. Capability layer: `McpClientManager` + LinkedIn, Exa, Jina adapters.
5. Strategy + job intelligence services.
6. CV/application/approval/follow-up services (reuse v1 phases 5–7, 11–12).
7. Learning engine + analytics.
8. Channels: API polish, Telegram adapter, CLI.
9. Hardening: security review, load/cost tests, E2E suite.
