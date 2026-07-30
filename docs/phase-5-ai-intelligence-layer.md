# Phase 5: AI Intelligence Layer

## Overview

Phase 5 delivers the **AI Intelligence Layer** — an optional, provider-abstracted AI subsystem that generates human-readable communication artifacts (match explanations, tailored resumes, cover letters, application emails) from the structured recommendation and profile data produced by Phases 1–4.

The layer is designed with a strict separation of concerns:

| Role | Technology |
|---|---|
| Filtering, matching, scoring, ranking, status transitions, business rules | **Python (deterministic)** — Phases 2, 3, 4 |
| Human-readable communication (explanations, prose, emails) | **AI (LLM)** — Phase 5 only |

**AI is advisory only.** It never makes hiring decisions, never changes scores, never overrides hard rules, and never modifies persisted recommendation data. All AI-generated content requires human review before use.

---

## Architecture

### Layer Diagram

```
app/domain/ai/                         <-- Domain: frozen dataclass entities, enums, error types
app/config/ai.toml + ai_config.py      <-- Configuration: provider model, temperature, timeouts, retries, feature toggles
app/infrastructure/ai/                 <-- Infrastructure: AIProvider (ABC), GeminiProvider
app/services/prompt_service.py         <-- Services: load, render, version-extract prompt templates
app/services/output_validator.py       <-- Services: deterministic validation (empty, short, injection, JSON schema)
app/services/token_tracker.py          <-- Services: persist token usage to ai_token_usage table, cost estimation
app/services/ai_orchestrator.py        <-- Services: single entry point for all AI features
app/services/explanation_service.py    <-- Services: generate human-readable match explanations
app/services/resume_tailor_service.py  <-- Services: tailor resume sections for a specific job
app/services/cover_letter_service.py   <-- Services: generate personalized cover letter
app/services/email_draft_service.py    <-- Services: draft application email (subject, body, signature)
prompts/*.md                           <-- 4 versioned prompt template files with front-matter metadata
app/db/models/ai_usage.py              <-- Persistence: TokenUsageRecord ORM model
app/cli/commands.py                    <-- CLI: 6 ai subcommands
```

### Strict Boundary

Phase 5 components **never** access:
- Job matching/filtering/duplicate tables
- Recommendation scoring logic
- Hard rule evaluation
- Profile validation decisions
- Email sending or Telegram (both remain future)

Phase 5 **only** reads:
- Structured `Recommendation` entities (in memory, via service injection)
- `MasterProfile` entities (in memory, via service injection)
- `CoverLetter` entities (in memory, via service injection)

---

## Configuration

### `app/config/ai.toml`

```toml
[provider]
name = "gemini"
model = "gemini-2.0-flash-lite"
temperature = 0.7
max_output_tokens = 1024
timeout_seconds = 30
retry_count = 2

[features]
explanations = true
resume_tailoring = true
cover_letter = true
email_draft = true
```

### `app/config/ai_config.py`

The TOML file is loaded into a frozen `AIConfig` dataclass with two nested configs:

| Class | Fields |
|---|---|
| `AIProviderConfig` | `name`, `model`, `temperature`, `max_output_tokens`, `timeout_seconds`, `retry_count` |
| `AIFeaturesConfig` | `explanations`, `resume_tailoring`, `cover_letter`, `email_draft` |
| `AIConfig` | `provider: AIProviderConfig`, `features: AIFeaturesConfig` |

Loaded via `get_ai_config()` with `lru_cache(maxsize=1)`.

### `app/config/settings.py`

Two API key settings added to the existing Pydantic `Settings`:

| Setting | `.env` Key | Purpose |
|---|---|---|
| `gemini_api_key` | `GEMINI_API_KEY` | Gemini API authentication |
| `openrouter_api_key` | `OPENROUTER_API_KEY` | Reserved for future OpenRouter integration |

---

## Domain Layer

### Entities (`app/domain/ai/entities.py`)

All entities are `@dataclass(frozen=True, slots=True)`:

| Entity | Purpose | Key Fields |
|---|---|---|
| `AIResponse` | Raw response from an AI provider | `text`, `provider`, `model`, `input_tokens`, `output_tokens`, `latency_ms` |
| `TokenUsage` | Token usage record for persistence | `provider`, `model`, `feature`, `prompt_version`, `input_tokens`, `output_tokens`, `latency_ms`, `estimated_cost` |
| `ExplanationResult` | Result of explanation generation | `explanation`, `recommendation_id` |
| `TailoredResume` | Result of resume tailoring | `sections: dict[str, str]`, `source_profile_version` |
| `CoverLetter` | Generated cover letter | `body`, `recipient_name`, `company_name` |
| `EmailDraft` | Generated email draft | `subject`, `body`, `recipient`, `signature` |

### Enums (`app/domain/ai/enums.py`)

```python
class AIProviderName(StrEnum):
    GEMINI = "gemini"
    OPENAI = "openai"
    CLAUDE = "claude"
    OLLAMA = "ollama"


class AIFeature(StrEnum):
    EXPLANATION = "explanation"
    RESUME_TAILORING = "resume_tailoring"
    COVER_LETTER = "cover_letter"
    EMAIL_DRAFT = "email_draft"
```

### Errors (`app/domain/ai/errors.py`)

| Exception | Base | When Raised |
|---|---|---|
| `AIError` | `Exception` | Base error for all AI operations |
| `ProviderError` | `AIError` | Network, auth, rate-limit, or API errors |
| `ValidationError` | `AIError` | AI output failed deterministic validation |
| `ConfigurationError` | `AIError` | AI configuration is missing or invalid |
| `PromptError` | `AIError` | Prompt loading or rendering failed |
| `TokenTrackingError` | `AIError` | Token usage persistence failed |

---

## Infrastructure: AI Provider Abstraction

### Abstract Interface (`app/infrastructure/ai/abstract.py`)

```python
class AIProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, **kwargs: object) -> AIResponse: ...
```

The ABC defines a single method that receives a fully rendered prompt string and returns a frozen `AIResponse` with text and usage metadata. Implementations handle:
- Authentication (API key retrieval)
- Request formatting (model, temperature, max tokens)
- Response parsing (text extraction, token counts from usage metadata)
- Error mapping (network failures, rate limits, auth errors)

### Gemini Implementation (`app/infrastructure/ai/gemini_provider.py`)

Uses the `google-genai>=1.0.0` SDK with `genai.Client`:

- Reads `gemini_api_key` from `Settings`
- Uses `client.models.generate_content()` with config dict
- Extracts `usage_metadata.prompt_token_count` and `candidates_token_count` for tracking
- Wraps all provider exceptions in `ProviderError`
- Measures wall-clock latency in milliseconds

### Adding a New Provider

To add a new provider (e.g., OpenAI, Claude, Ollama, AzureOpenAI):

1. Create `app/infrastructure/ai/openai_provider.py` implementing `AIProvider`
2. Add API key to `Settings` (e.g., `openai_api_key`)
3. Add provider name to `AIProviderName` enum
4. Add `elif cfg.name == "openai":` branch in `AIOrchestrator._build_provider()`
5. Update `provider.name` in `ai.toml`

No other code changes needed. The orchestrator, validators, services, CLI, and prompt system are all provider-agnostic.

---

## Prompt System

### Prompt Files (`prompts/*.md`)

Four versioned prompt template files, each with YAML-style front-matter metadata:

| File | Prompt Name | Version | Purpose |
|---|---|---|---|
| `match_explanation.md` | `match_explanation` | 1.0 | Generate human-readable explanation of why a job matches the profile |
| `resume_tailoring.md` | `resume_tailoring` | 1.0 | Tailor resume sections for a specific job description |
| `cover_letter.md` | `cover_letter` | 1.0 | Generate a personalized cover letter |
| `email_application.md` | `email_application` | 1.0 | Draft an application email with subject, body, and signature |

### Front-Matter Metadata

Each prompt file begins with front matter:

```
---
version: 1.0
purpose: Brief description of what this prompt does
inputs:
  - input_name: description
output: Description of expected output format
---
```

### PromptService (`app/services/prompt_service.py`)

| Method | Description |
|---|---|
| `load_prompt(name)` | Load raw template text by name from `prompts/` directory |
| `render(name, variables)` | Load template and substitute variables via `string.Template.safe_substitute()` |
| `get_version(name)` | Extract `version:` line from front matter |
| `list_prompts()` | List all available prompts with name, file, version, purpose |

All variables are pre-serialized to strings before rendering. Missing variables are left as-is (safe substitute).

### Adding a New Prompt

1. Create `prompts/new_feature.md` with front-matter metadata and `$variable` placeholders
2. Add `"new_feature": "new_feature.md"` to `_PROMPT_FILES` in `prompt_service.py`
3. Add `AIFeature.NEW_FEATURE` to `app/domain/ai/enums.py`
4. Enable in `ai.toml` `[features]` section
5. Build the service and CLI handler

---

## Orchestrator & Services

### AIOrchestrator (`app/services/ai_orchestrator.py`)

The single entry point for all AI features. It implements a pipeline:

```
generate_text()
  1. PromptService.load_prompt(name)          -- load template
  2. PromptService.render(name, variables)    -- substitute variables
  3. AIProvider.generate(rendered, **kwargs)  -- call AI model
  4. OutputValidator.validate_text(text)      -- validate output
  5. TokenTracker.track(...)                  -- persist usage
  6. return text

generate_json()
  1. generate_text()                           -- same pipeline
  2. OutputValidator.validate_json(text, fields) -- JSON parse + schema check
  3. return dict
```

Two public methods:

| Method | Returns | Use Case |
|---|---|---|
| `generate_text(prompt_name, variables, feature, ...)` | `str` | Free-text generation (explanations, cover letters) |
| `generate_json(prompt_name, variables, feature, required_fields, ...)` | `dict[str, object]` | Structured generation (resume sections, email drafts) |

Provider selection is automatic based on `ai.toml` `[provider]` name, with `GeminiProvider` as the default.

### ExplanationService (`app/services/explanation_service.py`)

| Method | Description |
|---|---|
| `explain(recommendation, job_title, company)` | Generate human-readable NL explanation of a recommendation's score breakdown, matched/missing items |

Receives a structured `Recommendation` entity and calls `AIOrchestrator.generate_text()` with `prompt_name="match_explanation"` and `feature=EXPLANATION`.

### ResumeTailorService (`app/services/resume_tailor_service.py`)

| Method | Description |
|---|---|
| `tailor(profile, recommendation, job_description)` | Generate tailored resume sections reordered and rewritten for a specific job |

Calls `AIOrchestrator.generate_json()` with `prompt_name="resume_tailoring"` and `feature=RESUME_TAILORING`. Validates JSON response has required fields: `summary`, `skills`, `experience`, `projects`.

### CoverLetterService (`app/services/cover_letter_service.py`)

| Method | Description |
|---|---|
| `generate(profile, recommendation, company, recipient)` | Generate a personalized cover letter body text |

Calls `AIOrchestrator.generate_text()` with `prompt_name="cover_letter"` and `feature=COVER_LETTER`.

### EmailDraftService (`app/services/email_draft_service.py`)

| Method | Description |
|---|---|
| `draft(cover_letter, company, job_title, recipient, candidate_name)` | Generate a full email draft with subject, body, and signature |

Calls `AIOrchestrator.generate_json()` with `prompt_name="email_application"` and `feature=EMAIL_DRAFT`. Validates JSON response has required fields: `subject`, `body`, `signature`.

---

## Output Validation

### OutputValidator (`app/services/output_validator.py`)

Fully deterministic validation — no ML, no heuristics, no second AI model.

| Check | Method | Rejects |
|---|---|---|
| Empty output | `validate_text()` | Blank or whitespace-only text |
| Too short | `validate_text()` | Text under `MIN_TEXT_LENGTH` (10 chars) |
| Prompt injection patterns | `validate_text()` → `_check_injection()` | 5 regex patterns matching "ignore previous instructions", "forget all prompts", "system prompt", "you are now free", "do whatever" |
| Invalid JSON | `validate_json()` | Non-parseable JSON |
| Wrong type | `validate_json()` | JSON that is not a dict |
| Missing fields | `validate_json()` → `required_fields` | Absent or empty/null required fields |

The injection regex patterns are case-insensitive and search anywhere in the text. Matches are capped at 60 chars in the error message.

---

## Token Tracking

### TokenTracker (`app/services/token_tracker.py`)

Records every AI API call to the `ai_token_usage` table for cost analytics and auditing.

| Method | Description |
|---|---|
| `track(provider, model, feature, prompt_version, input_tokens, output_tokens, latency_ms)` | Persist a usage record and return a `TokenUsage` domain entity |
| `get_usage(limit=50, feature=None)` | Retrieve recent usage records, optionally filtered by feature |

Cost estimation uses a hardcoded rate table per model (currently `$0.075/1K input tokens` for `gemini-2.0-flash-lite`). Only input tokens are counted for cost estimation.

### DB Model (`app/db/models/ai_usage.py`)

| Column | Type | Notes |
|---|---|---|
| `id` | INT (PK, auto) | |
| `provider` | VARCHAR(50) | "gemini" |
| `model` | VARCHAR(100) | "gemini-2.0-flash-lite" |
| `feature` | VARCHAR(50) | Indexed. One of `AIFeature` values |
| `prompt_version` | VARCHAR(20) | Extracted from prompt front matter |
| `input_tokens` | INT | From provider usage metadata |
| `output_tokens` | INT | From provider usage metadata |
| `latency_ms` | INT | Wall-clock milliseconds |
| `estimated_cost` | FLOAT | USD estimate based on input tokens |
| `created_at` | DATETIME | Server default `now()` |

### Migration

**Alembic revision:** `1f98f9326bb1_create_ai_token_usage_table.py`

Applied to MySQL and verified current.

---

## CLI

Six new subcommands under `stagepilot ai`:

### `stagepilot ai explain <recommendation_id> [--job-title] [--company]`

Generate human-readable explanation for a specific recommendation.

```bash
uv run stagepilot ai explain 1 --job-title "Engineer" --company "Acme"
```

### `stagepilot ai tailor-resume <recommendation_id> [--job-description]`

Generate a tailored resume for a specific recommendation.

```bash
uv run stagepilot ai tailor-resume 1 --job-description "Python dev with 5 years"
```

### `stagepilot ai cover-letter <recommendation_id> [--company] [--recipient]`

Generate a personalized cover letter.

```bash
uv run stagepilot ai cover-letter 1 --company "Acme" --recipient "HR"
```

### `stagepilot ai email <recommendation_id> [--company] [--job-title] [--recipient]`

Draft an application email with subject, body, and signature.

```bash
uv run stagepilot ai email 1 --company "Acme" --job-title "Engineer" --recipient "HR"
```

### `stagepilot ai usage [--limit N] [--feature FEATURE]`

Show AI token usage and cost analytics.

```bash
uv run stagepilot ai usage --limit 10
uv run stagepilot ai usage --feature explanation
```

### `stagepilot ai prompts`

List available AI prompts with metadata (name, version, purpose).

```bash
uv run stagepilot ai prompts
```

---

## Persistence

### New Table: `ai_token_usage`

Created by migration `1f98f9326bb1`. See DB Model section above for schema.

---

## Design Decisions

### AI is Advisory Only

The entire Phase 5 design enforces that AI is used exclusively for **human-readable communication**. No AI-generated text feeds back into filtering, matching, scoring, ranking, or status transitions. Python remains the sole source of truth for all business logic.

### Provider Abstraction

The `AIProvider` ABC allows future provider swaps with minimal code changes. Only five lines need to change to switch from Gemini to OpenAI: the provider implementation file, the enum entry, the `_build_provider()` branch, and the config. All 46 AI tests are written against `MagicMock` and do not require a real provider.

### Versioned Prompt Files

Prompts are stored as flat `.md` files with front-matter metadata rather than inline strings or database rows. This gives:

- **Git-tracked versioning** — every prompt change is visible in git history
- **Editability** — non-developers can read and edit prompts without touching Python
- **Separation of concerns** — prompt changes do not require code deploys

### Deterministic Output Validation

Output validation is purely rule-based (regex, JSON parsing, length checks). No AI model is used to evaluate AI output. This ensures:

- **Zero additional cost** — no second API call for evaluation
- **Predictable behavior** — same output always passes or fails the same way
- **No circular dependency** — validation does not depend on the same providers it validates

### No Hardcoded Prompts

Every prompt text lives in a file under `prompts/`, registered in `_PROMPT_FILES` dict in `prompt_service.py`. No prompt string is embedded in Python source code. This makes prompts auditable, versionable, and independently editable.

### Token Usage Tracking

Every AI API call is recorded in `ai_token_usage` with provider, model, feature, token counts, latency, and estimated cost. This enables:

- Cost analysis per feature
- Latency monitoring
- Usage auditing
- Prompt version effectiveness comparison

### Feature Toggling

Each AI feature can be independently enabled or disabled in `ai.toml` `[features]`. Disabled features skip the AI call and return a fallback message. This allows gradual rollout and cost control.

---

## Design Constraints

### Must Not Do

- AI must never modify or override deterministic matching, filtering, or scoring results
- AI must never send emails or make external calls beyond the configured LLM API
- AI must never persist data to tables outside `ai_token_usage`
- AI must never make business logic decisions (accept/reject, score change, status change)
- AI must never access the database directly (only through service injection)

### Must Do

- All AI outputs must pass deterministic validation before being returned to the caller
- All AI API calls must be tracked in `ai_token_usage` for cost and usage analytics
- All prompts must be versioned `.md` files with front-matter metadata
- All provider implementations must implement the `AIProvider` ABC

---

## Test Coverage

46 new tests across 5 test files:

| Test File | Tests | Coverage |
|---|---|---|
| `test_prompt_service.py` | 9 | Loading, rendering, version extraction, listing, error cases |
| `test_output_validator.py` | 16 | Empty/short rejection, injection detection, JSON schema validation, edge cases |
| `test_token_tracker.py` | 6 | Track persist, get_usage, cost estimation, error handling |
| `test_ai_orchestrator.py` | 7 | Full pipeline, provider selection, config errors |
| `test_ai_services.py` | 8 | All 4 services: returns correct types, calls orchestrator with correct params |

All tests use `MagicMock` for provider/orchestrator — no real API keys or network access required.

---

## Future Directions

- Add `OpenAIProvider` (GPT-4o) and `ClaudeProvider` (Claude 3.5 Sonnet) implementations
- Add OpenRouter multi-provider routing
- Add streaming output for real-time CLI display
- Add prompt version comparison and A/B testing
- Add semantic output validation via embedding similarity
- Add rate limiting and request queuing for batch processing
- Add caching for identical prompt+variable combinations
- Add export usage analytics to CSV
- Expose AI features via REST API endpoints (future Phase)
