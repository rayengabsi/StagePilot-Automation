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
```

- `refresh` fetches and ingests jobs from one source immediately.
- `health` runs a connectivity check and reports status + latency.
- `test` validates the source configuration and dry-runs a fetch (no persistence).

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
- `test_multi_provider_discovery.py` (integration) — multi-provider ingestion + cross-provider dedupe

## Adding a New Provider

1. Add a `JobSourceType` enum entry.
2. Subclass `BaseJobSourceConnector`; implement `normalize()` and `_fetch_page()`.
3. Register the class in `_ALL_CONNECTORS` in `registry.py`.
4. Add a `[providers.<name>]` section in `providers.toml` and the `enabled` list.
5. Add a `sources add-<name>` CLI subcommand (optional).
6. Add tests mirroring `test_provider_connectors.py`.
