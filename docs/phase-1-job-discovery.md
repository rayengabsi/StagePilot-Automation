# Phase 1 Job Discovery

Phase 1 delivers the first working job ingestion milestone.

## Scope

```text
Source -> Fetch -> Normalize -> Persist raw_jobs -> Persist jobs -> Log -> Test
```

Out of scope:

- Hard filtering
- Similarity scoring
- AI analysis
- Resume generation
- Telegram approval
- Email sending

## Source Type

The first connector supports RSS and Atom feeds. Browser automation is intentionally avoided.

## Duplicate Protection

Raw duplicate protection uses:

- Existing `(source_id, external_id)` lookup when `external_id` is present.
- Unique `(source_id, content_hash)` database constraint.

Normalized job duplicate protection uses:

- Unique `(source_id, normalized_hash)` database constraint.

## Local Verification

```bash
uv run alembic upgrade head
uv run stagepilot sources add-rss --name "Example Jobs" --url "https://example.com/jobs.xml"
uv run stagepilot sources list
uv run stagepilot discover
uv run ruff check .
uv run ruff format --check .
uv run pytest
```
