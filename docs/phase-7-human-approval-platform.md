# Phase 7: Human Approval Platform

## Architecture

The Human Approval Platform sits between the Document Rendering Engine and the outside world. It guarantees that no internship application can ever be submitted without explicit human approval.

```
Recommendation Engine → AI Intelligence → Document Rendering → Application Package
                                                                    ↓
                                                            Approval Queue
                                                                    ↓
                                                           Approval Service
                                                         /        |        \
                                                   Telegram  Web UI  Future API
```

**Key design principle:** `ApprovalService` owns all business logic. Telegram (and future UIs) are thin adapters that call `ApprovalService` only.

---

## ApplicationPackage Design

`ApplicationPackage` (`app/domain/approval/entities.py`) is a frozen dataclass containing everything needed to reproduce an application:

- `recommendation_id`, `job_id`, `profile_id` — foreign keys
- `final_score` — the AI recommendation score
- `snapshot_json` — immutable JSON snapshot of the full application state
- `documents_json` — JSON of rendered document paths
- `application_hash` — SHA-256 deterministically computed from snapshot + documents
- `profile_version`, `template_name`, `theme_name` — versioning metadata
- `status` — current `ApprovalState`
- `priority`, `revision_number` — queue management
- `telegram_message_id` — optional link to Telegram message
- Timestamps: `created_at`, `updated_at`, `approved_at`, `reviewed_at`

### Snapshot Engine (`app/domain/approval/package.py`)

Every package entering the queue creates an immutable snapshot containing:
- Recommendation data (job, matched/missing skills, explanation)
- Profile data
- Tailored resume, cover letter body, email draft
- Rendered PDF/DOCX paths
- Template and theme names
- Configuration version
- Timestamp

The `application_hash` ensures reproducibility and prevents duplicate submissions.

---

## Approval State Machine

**States** (8 total):

```
NEW → QUEUED → UNDER_REVIEW → APPROVED → ARCHIVED
                              → REJECTED → QUEUED
                                         → ARCHIVED
                              → REVISION_REQUESTED → QUEUED
                                                   → ARCHIVED
                    → SKIPPED → QUEUED
                              → ARCHIVED
         → ARCHIVED
```

**Transition validation** (`app/domain/approval/enums.py:is_valid_transition`):
- Every transition is explicitly defined in `VALID_TRANSITIONS`
- Invalid transitions raise `InvalidTransitionError`
- Duplicate approvals raise `DuplicateApprovalError`
- Self-transitions are impossible

---

## Queue Engine (`app/services/queue_service.py`)

Supports 5 strategies:
- `FIFO` — first in, first out (default)
- `HIGHEST_SCORE` — highest recommendation score first
- `DEADLINE_PRIORITY` — earliest deadline first
- `NEWEST_FIRST` — by creation date descending
- `OLDEST_FIRST` — by creation date ascending

Features:
- Configurable queue limit (default: 50)
- Pagination (offset/limit)
- Filtering by status
- Automatic enqueue/dequeue

---

## Approval Service (`app/services/approval_service.py`)

UI-independent service that owns all business logic:

| Method | Description |
|--------|-------------|
| `create_package()` | Save new package + audit event |
| `enqueue()` | Add package to queue + state transition |
| `dequeue()` | Remove from queue |
| `approve()` | Approve + audit + dequeue |
| `reject()` | Reject + audit + dequeue |
| `request_revision()` | Request revision + audit + dequeue |
| `skip()` | Skip + audit + dequeue |
| `archive()` | Archive + audit + dequeue |
| `start_review()` | Mark as UNDER_REVIEW |
| `get_documents()` | Retrieve document paths |
| `get_snapshot()` | Retrieve immutable snapshot |
| `get_history()` | Full audit log for a package |
| `add_comment()` | Add timestamped comment |

---

## Database Schema

4 tables created in migration `2a9350fa7ece`:

### `application_packages`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | PK |
| recommendation_id | INTEGER | FK → recommendations |
| job_id | INTEGER | FK → jobs |
| profile_id | INTEGER | FK → profiles |
| final_score | FLOAT | |
| status | VARCHAR(30) | Indexed |
| priority | INTEGER | |
| revision_number | INTEGER | |
| telegram_message_id | INTEGER | Nullable |
| snapshot_json | TEXT | |
| documents_json | TEXT | |
| application_hash | VARCHAR(64) | Unique |
| profile_version | VARCHAR(50) | |
| template_name | VARCHAR(50) | |
| theme_name | VARCHAR(50) | |
| created_at | DATETIME | |
| updated_at | DATETIME | |
| approved_at | DATETIME | Nullable |
| reviewed_at | DATETIME | Nullable |

### `approval_queue`
One-to-one with `application_packages`. Tracks queue order, score, deadline.

### `approval_events`
Full audit log: action, actor, comment, previous/new state.

### `approval_comments`
Timestamped comments from reviewers.

---

## Telegram Architecture

**No business logic.** The Telegram client (`app/infrastructure/telegram/`) is a thin adapter:

| Component | File | Responsibility |
|-----------|------|----------------|
| `bot.py` | `run_telegram_bot()` | Polling loop, register handlers |
| `handlers.py` | `build_handlers()` | Command + callback handlers |
| `messages.py` | Message template functions | Telegram Markdown presentation only |
| `auth.py` | `TelegramAuth` | User authorization |

### Commands
`/start`, `/help`, `/queue`, `/view`, `/open`, `/approve`, `/reject`, `/revise`, `/skip`, `/archive`, `/history`, `/status`

### Inline Buttons

Every application keeps the same approval actions, grouped into short action rows:

```text
✅ Approve        📄 Preview Resume
✉️ Preview Cover Letter   🔗 Open Job
🕘 Application History    🧾 Email Draft
🔁 Request Revision       ⏭️ Skip       ❌ Reject
🗄️ Archive
```

If the job URL is unavailable, `Open Job` gracefully becomes `Package Details`. The Telegram adapter still calls `ApprovalService`; no approval workflow logic lives in the bot.

### Message Format

Telegram messages are formatted as compact Markdown cards, not raw JSON or CLI output. All templates live in `app/infrastructure/telegram/messages.py` and are presentation-only helpers.

Main recommendation cards show:

- Professional header: company, position, location, work mode
- Prominent match score and confidence
- Lifecycle progress: `Discovered → Recommended → Tailored → Approved → Applied`
- Concise `Why This Matches You`
- Compact `Missing Skills`
- Job summary: employment type, seniority, posting date
- AI tailoring quality and resume quality when present in the approval snapshot
- Available document previews
- Queue position, status, template, and revision metadata

Example:

```text
🚀 *StagePilot Recommendation*
━━━━━━━━━━━━━━━━━━━━
🏢 *Acme Corp*
💼 Backend Engineer
📍 Paris  •  Remote

🎯 *Match Score:* `92.5/100`
🧭 *Confidence:* `Very High`
📍 *Progress:* ● ● ● ○ ○  `Discovered → Recommended → Tailored → Approved → Applied`

✨ *Why This Matches You*
• Strong Python and SQL match for the role.

🧩 *Missing Skills*
• Go

📋 *Job Summary*
• Employment: Internship
• Seniority: Junior
• Posted: 2026-08-01

🧪 *Tailoring Quality*
• AI Tailoring: `84.5/100` Good
• Resume Quality: `91.2/100` Excellent
```

Additional reusable templates cover application updates, follow-up reminders, interview invitations, offers, rejections, daily summaries, queue views, document previews, package details, package status, and application history. Each template degrades gracefully when optional information is missing by showing concise fallback text such as `Not specified`.

---

## Security

- **Authorization:** `TelegramAuth.authorize()` validates user ID against `allowed_chat_ids`
- **Unknown users:** Rejected with "Unauthorized" message
- **State validation:** Every transition checked against `VALID_TRANSITIONS`
- **Duplicate prevention:** `DuplicateApprovalError` on double-approve
- **Snapshot integrity:** `application_hash` SHA-256 prevents tampering

---

## CLI

```
stagepilot approval queue    -- Show queue
stagepilot approval list     -- List packages
stagepilot approval approve  -- Approve package
stagepilot approval reject   -- Reject package
stagepilot approval revise   -- Request revision
stagepilot approval skip     -- Skip package
stagepilot approval archive  -- Archive package
stagepilot approval history  -- Show package history
stagepilot telegram run      -- Start Telegram bot
```

---

## Error Handling

| Scenario | Handling |
|----------|----------|
| Telegram unavailable | Bot fails to start, error logged |
| Database unavailable | SQLAlchemy raises, caught by CLI/Telegram |
| Deleted Telegram message | Handler checks `effective_message` |
| Duplicate callback | `query.answer()` prevents double-processing |
| Expired approval | `approval_timeout_hours` config (48h default) |
| Missing documents | `DocumentNotFoundError` raised |
| Rollback failures | `session_scope()` context manager handles rollback |

---

## Files Created

| File | Lines |
|------|-------|
| `app/domain/approval/__init__.py` | Package exports |
| `app/domain/approval/enums.py` | ApprovalState, ApprovalAction, QueueStrategy, VALID_TRANSITIONS |
| `app/domain/approval/errors.py` | 9 error classes |
| `app/domain/approval/entities.py` | ApplicationPackage, ApprovalEvent, ApprovalComment |
| `app/domain/approval/package.py` | Snapshot builder, hash, package factory |
| `app/config/approval.toml` | Queue/snapshot/notification config |
| `app/config/telegram.toml` | Bot token, auth, formatting config |
| `app/config/approval_config.py` | ApprovalConfig loader |
| `app/config/telegram_config.py` | TelegramConfig loader |
| `app/db/models/approval.py` | 4 ORM models |
| `app/db/repositories/approval.py` | 4 repositories |
| `app/services/approval_service.py` | ApprovalService (all business logic) |
| `app/services/snapshot_service.py` | SnapshotService |
| `app/services/queue_service.py` | QueueService (5 strategies) |
| `app/infrastructure/telegram/__init__.py` | Package init |
| `app/infrastructure/telegram/auth.py` | TelegramAuth (authorization) |
| `app/infrastructure/telegram/messages.py` | Message formatter |
| `app/infrastructure/telegram/handlers.py` | 14 command + callback handlers |
| `app/infrastructure/telegram/bot.py` | Bot runner |
| `alembic/versions/2a9350fa7ece_create_approval_tables.py` | Migration |
| `tests/unit/test_approval_state_machine.py` | 10 tests |
| `tests/unit/test_approval_package.py` | 6 tests |
| `tests/unit/test_approval_snapshot.py` | 5 tests |
| `tests/unit/test_approval_config.py` | 3 tests |
| `tests/unit/test_approval_service.py` | 12 tests |
| `tests/unit/test_approval_queue.py` | 4 tests |
| `tests/unit/test_approval_telegram_auth.py` | 4 tests |
| `tests/unit/test_approval_telegram_messages.py` | 8 tests |
| `tests/unit/test_approval_cli.py` | 6 tests |
| `tests/unit/test_approval_migration.py` | 5 tests |
| `docs/phase-7-human-approval-platform.md` | This documentation |

---

## Test Summary

- **63 new tests** across 10 test files
- **259 total tests** passing
- Coverage: state machine, entities, snapshots, service, queue, CLI, Telegram auth, Telegram messages, migration, config

## Ruff Summary

`ruff check .` — All checks passed (0 errors, 0 warnings)

## Alembic Summary

Head: `2a9350fa7ece` (create_approval_tables)
Depends on: `1f98f9326bb1`

## Known Limitations

1. Telegram bot requires a valid `bot_token` in `config/telegram.toml` to run
2. No Web UI or Slack/Discord adapters yet — future phases
3. Auto-archive is configured but not implemented as a background job
4. The snapshot engine stores rendered document paths (not the file contents) — files must remain accessible
