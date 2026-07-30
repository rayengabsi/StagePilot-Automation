# StagePilot Automation

AI-powered, human-in-the-loop internship automation platform.

## Status

Phase 0 foundation is implemented. No business pipeline logic exists yet.

## Architecture

The project is a modular monolith using Clean Architecture and Domain-Driven Design boundaries.

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

## Run

```bash
uv run stagepilot
```

## Job Discovery

Apply migrations before using discovery commands:

```bash
uv run alembic upgrade head
```

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

Phase 1 discovery only fetches, normalizes, stores, logs, and skips ingestion duplicates. It does not filter, score, call AI, generate resumes, send Telegram messages, or send emails.

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
