# Phase 8 — Multi-Provider Job Discovery Platform

Phase 8 transforms discovery from a single RSS feed reader into a production-grade,
multi-provider platform. It adds connectors for nine provider families, a shared
HTTP/rate-limiting infrastructure, provider configuration, per-source observability,
and full source-management CLI commands.

## Provider Connectors

Each provider is implemented as a `BaseJobSourceConnector` subclass under
`app/infrastructure/job_sources/` and is registered by `provider_name`:

| Connector | Provider name | Source type | Auth / config |
|---|---|---|---|
| `RssFeedConnector` | `rss` | `rss_feed` | none |
| `GreenhouseConnector` | `greenhouse` | `greenhouse` | `token` or board token from `base_url` path |
| `LeverConnector` | `lever` | `lever` | `company` slug or from `base_url` path |
| `AshbyConnector` | `ashby` | `ashby` | `board` identifier or from `base_url` path |
| `SmartRecruitersConnector` | `smart_recruiters` | `smart_recruiters` | `company` alias or from `base_url` path |
| `TeamtailorConnector` | `teamtailor` | `teamtailor` | `api_key` |
| `WelcomeToTheJungleConnector` | `welcome_to_the_jungle` | `welcome_to_the_jungle` | `slug` or from `base_url` path |
| `RemoteOkConnector` | `remote_ok` | `remote_ok` | none |
| `WellfoundConnector` | `wellfound` | `wellfound` | optional `token` |
| `CompanyPagesConnector` | `company_pages` | `company_pages` | CSS selectors (see below) |

All connectors implement `fetch()`, `discover()`, `validate()`, `health()`, and
`normalize()` from the shared base class. Pagination is cursor-based and handled by
`PageResult(items, next_cursor)`.

### Company career pages

`CompanyPagesConnector` scrapes generic career pages using configurable CSS selectors:

- `job_links_selector` (required) — anchors to individual job posts
- `list_url` — listing page URL (defaults to `base_url`)
- `next_page_selector` — pagination link selector (optional)
- `title_selector` / `description_selector` — detail page selectors (optional)
- `scrape_details` — fetch each job detail page (default `true`)
- `max_pages` — maximum listing pages to crawl (default `1`)

When no `description_selector` is configured, the connector falls back to JSON-LD
`JobPosting` structured data.

## Shared Infrastructure

### HTTP client (`app/infrastructure/http/client.py`)

One `HttpClient` instance is shared by all connectors:

- `requests.Session` with connection pooling (10 connections)
- Tenacity retries with exponential backoff (1s → 8s)
- Retries on `429/500/502/503/504` and transient `Timeout`/`ConnectionError` exceptions
- Per-provider timeout, retry budget, and base headers from `providers.toml`
- `User-Agent` injected on every request

### Rate limiting (`rate_limiter.py`)

`RateLimiter(min_interval_seconds)` enforces a minimum delay between paginated
requests. Each provider's interval comes from `app/config/providers.toml`.

### HTML parsing (`app/infrastructure/html/parsing.py`)

lxml + BeautifulSoup helpers: `parse_html`, `css_select`, `css_select_first`,
`xpath_select`, `extract_metadata`, `extract_json_ld`, `extract_text`,
`extract_attr`, `extract_href`, `resolve_url`.

### Shared utils (`utils.py`)

`parse_datetime`, `parse_epoch_millis`, `clean_text`, `strip_html`.

## Configuration

`app/config/providers.toml` controls provider behavior:

```toml
[defaults]
timeout_seconds = 20
retry_attempts = 3
min_interval_seconds = 0.5
rate_limit_per_minute = 60

[providers]
enabled = ["rss", "greenhouse", "lever", "ashby", "smart_recruiters", ...]

[providers.greenhouse]
enabled = true
timeout_seconds = 20
retry_attempts = 3
min_interval_seconds = 0.5
rate_limit_per_minute = 30
base_headers = {}
```

`ProvidersConfig.for_provider(name)` returns the effective config, falling back to
`[defaults]` for unlisted providers. `build_connector_registry(settings)` auto-registers
every connector whose provider is enabled — the CLI, `PipelineOrchestrator`, and any
other caller never list providers by hand.

## Registry

`app/infrastructure/job_sources/registry.py` exposes:

- `ConnectorRegistry(connectors)` — maps `JobSourceType` → connector instance
- `get_connector_class(provider_name)` — resolves a provider name to a class
- `build_connector_registry(settings, config=None)` — builds the full registry

`PipelineOrchestrator._run_discovery()` and the `discover` CLI command both use
`build_connector_registry`, so new providers are picked up automatically.

## Enriched Job Metadata

Discovered and normalized jobs now carry additional metadata:

- `department`
- `employment_type`
- `remote_status` (`remote` / `hybrid` / `None`)
- `requirements`

These flow from each connector's `normalize()` through `JobNormalizationService` into
the `jobs` table columns `department`, `employment_type`, and `remote_status`
(migration `20260802_p8`).

## Job Intelligence Layer

Every normalized job is enriched with structured intelligence immediately after
normalization and before recommendation scoring (migration `20260802_p9` adds five
nullable `classification_*` columns to `jobs`):

| Column | Example values |
| --- | --- |
| `classification_specialization` | `backend`, `frontend`, `full_stack`, `mobile`, `devops`, `cloud`, `cybersecurity`, `ai_ml`, `data_engineering`, `qa`, `sre`, `platform`, `embedded`, `product` |
| `classification_seniority` | `intern`, `junior`, `mid`, `senior`, `lead`, `manager`, `director` |
| `classification_employment_type` | `internship`, `full_time`, `part_time`, `contract` |
| `classification_work_mode` | `remote`, `hybrid`, `onsite` |
| `classification_urgency` | `urgent` |

`JobClassificationService.classify(normalized_job)` derives these from configurable
keyword dictionaries in `app/config/classification.toml`:

- Keyword matching is case-insensitive and word-boundary based.
- Each keyword hit in the title is worth `title_weight` (3.0); each hit in the
  description/requirements is worth `body_weight` (1.0). The label with the highest
  weighted score wins, with ties resolved by dictionary order, and a label is only
  assigned when its score exceeds `min_score` (0.5).
- Seniority prefers the most senior matching level (e.g. "Senior Manager" is
  classified as `manager`, not `senior`).
- Work mode and urgency use direct keyword matches over the title, description,
  requirements, department, `employment_type`, `remote_status`, and location.
- English and French keyword variants are supported (e.g. `teletravail`/`télétravail`,
  `cdi`, `temps plein`, `stage`, `stagiaire`, `pfe`, `alternance`, `présentiel`,
  `sur site`, `hybride`).

The enrichment is provider-agnostic: new labels are added by editing the TOML with no
code changes. Original extracted values (`department`, `employment_type`,
`remote_status`) are preserved unchanged alongside the normalized classification.

`DiscoveryService` runs classification by default (constructor accepts an optional
`classifier`); `JobIngestionService.ingest()` persists the classification fields.
`SimilarityScorer` and `HardRuleMatcher` include the classification fields in the job
text used for matching, so enriched labels improve recommendation quality (e.g. a
`backend` specialization contributes to backend-skills matching even when the posting
wording is generic).

## Cross-Provider Duplicate Merging

`JobIngestionService` now detects duplicates by canonical URL across all sources, not
just within a single source. The same posting discovered through multiple providers
results in a single canonical `jobs` row; later postings are recorded as duplicates.
Source-scoped raw/normalized-hash checks remain in place for re-fetches of the same
source.

## Observability — `discovery_metrics`

`DiscoveryService` persists one `DiscoveryMetricRecord` per source per run:

- `run_id`, `source_id`, `source_name`, `provider`
- `jobs_fetched`, `jobs_inserted`, `duplicates`, `invalid`
- `accepted`, `rejected` (match counters delta for the source)
- `latency_ms`, `status` (`ok` / `failed`), `error`

`DiscoveryService.run_source(source)` runs discovery for a single source and records
the same metrics — used by `stagepilot sources refresh`.

### Error isolation

A failure in one provider never interrupts discovery for other sources. Per-job
failures (normalization or ingestion errors) increment the invalid counter and skip
that job; per-source failures (fetch or configuration errors) are isolated through
`_handle_source_failure`, which rolls back the transaction, records a `failed`
metric, and continues with the next configured source.

## Connector Validation Framework

`app/infrastructure/job_sources/validation.py` validates every existing connector
against mocked real-world scenarios with no network access:

- `NORMALIZED_JOB_SCHEMA` — the canonical 13-field `DiscoveredJob` contract every
  connector must emit (`external_id`, `url`, `title`, `company`, `location`,
  `description`, `raw_payload`, `discovered_at`, `posted_at`, `department`,
  `employment_type`, `remote_status`, `requirements`).
- `ConnectorValidator.validate_connector(connector, source=None)` rebuilds each
  connector with a fake HTTP client and runs its scenario suite.
- Per-provider scenario suites cover a happy path (with expected normalized fields),
  empty responses, malformed payloads, transport errors, and missing config
  (`validate` and `fetch` paths).
- `ConnectorBenchmarkResult` reports: `success_rate`, `avg_latency_ms` /
  `max_latency_ms`, `normalization_quality`, `duplicate_rate`, `error_handling`,
  `unhandled_errors`, and an `overall_score` (0–100) with `healthy` / `degraded` /
  `failed` status.
- When a real `JobSourceConfig` is passed, its configuration is also validated and an
  invalid config fails only that source.

`app/services/source_validation_service.py` turns those results into a health report:

- `SourceValidationService.benchmark_sources(source_configs)` — one
  `SourceBenchmarkEntry` per configured source; falls back to benchmarking every
  enabled provider when the list is empty.
- `SourcesHealthReport` aggregates entries into overall status, healthy/degraded/
  failed counts, and per-provider summaries. Everything is JSON-serializable via
  `to_dict()`.

## CLI — Source Management

```text
stagepilot sources add-rss --name "..." --url "..."
stagepilot sources add-greenhouse --name "Acme" --url "https://boards.greenhouse.io/acme" --token "acme"
stagepilot sources add-lever --name "Acme" --url "https://jobs.lever.co/acme" --company "acme"
stagepilot sources add-ashby --name "Acme" --url "https://jobs.ashbyhq.com/acme" --board "acme"
stagepilot sources add-smartrecruiters --name "Acme" --url "https://jobs.smartrecruiters.com/Acme" --company "Acme"
stagepilot sources add-teamtailor --name "Acme" --url "https://careers.acme.com" --api-key "..." --company "Acme"
stagepilot sources add-wttj --name "Acme" --url "https://www.welcometothejungle.com/fr/companies/acme" --slug "acme"
stagepilot sources add-remoteok --name "RemoteOK" --url "https://remoteok.com" --company "RemoteOK"
stagepilot sources add-wellfound --name "Startup" --url "https://wellfound.com/company/startup" --company "Startup"
stagepilot sources add-company --name "Acme" --url "https://acme.com/careers" --selector "a.job" [--list-url] [--max-pages N]
stagepilot sources list
stagepilot sources remove --id <id> | --name <name>
stagepilot sources enable --id <id> | --name <name>
stagepilot sources disable --id <id> | --name <name>
stagepilot sources refresh --id <id>
stagepilot sources health --id <id>
stagepilot sources test --id <id>
stagepilot sources benchmark
```

- `refresh` fetches and ingests jobs from one source immediately.
- `health` runs a connectivity check and reports status + latency.
- `test` validates the source configuration and dry-runs a fetch (no persistence).
- `benchmark` runs the connector validation benchmark across all configured sources
  and prints a JSON health report (success rate, response time, normalization
  quality, duplicate rate, error handling, overall status).

## Repository

`JobSourceRepository` now provides generic operations:

- `add_source(name, source_type, base_url, config, is_active=True)`
- `get_source(source_id)`, `get_source_by_name(name)`
- `remove_source(source_id)`
- `set_source_active(source_id, is_active)`
- `list_sources()`, `list_active_configs()`

## Tests

All connector, HTTP, parsing, and CLI tests are fully mocked — no network access.
Key coverage:

- `test_http_client.py` — headers, retries, transient failures, exhaustion
- `test_provider_connectors.py` — normalization + pagination for all 9 providers
- `test_html_parsing.py`, `test_providers_config.py`, `test_rate_limiter.py`
- `test_base_connector.py` — fetch loop, health, validate
- `test_registry_builder.py` — auto-registration and disabled providers
- `test_job_source_repository.py` — generic source operations
- `test_sources_cli.py` — source management CLI commands
- `test_connector_validation.py` — validation framework: every provider healthy,
  schema conformance, metrics, error handling, invalid-config failures
- `test_multi_provider_discovery.py` (integration) — multi-provider ingestion + cross-provider dedupe
- `test_provider_validation.py` (integration) — provider error isolation,
  benchmark reports, invalid-source failures

## Adding a New Provider

1. Add a `JobSourceType` enum entry.
2. Subclass `BaseJobSourceConnector`; implement `normalize()` and `_fetch_page()`.
3. Register the class in `_ALL_CONNECTORS` in `registry.py`.
4. Add a `[providers.<name>]` section in `providers.toml` and the `enabled` list.
5. Add a `sources add-<name>` CLI subcommand (optional).
6. Add a scenario suite in `_PROVIDER_SCENARIOS` in `validation.py` so the connector
   is covered by `stagepilot sources benchmark`.
7. Add tests mirroring `test_provider_connectors.py`.
