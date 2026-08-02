# Phase 12: Application Execution Engine

## Architecture

The Application Execution Engine starts after human approval. It turns an approved application package into a tracked job application with its own lifecycle, history, reminders, notes, labels, outcomes, and analytics.

```text
Recommendation -> AI Tailoring -> Rendering -> Approval Package
                                                    |
                                                    v
                                             Human Approval
                                                    |
                                                    v
                                           ApplicationService
                                                    |
       +----------------+------------------+--------+---------+
       |                |                  |                  |
  applications   application_events   reminders       notes/timeline/outcome
```

`ApplicationService` owns all application lifecycle business logic. Discovery, recommendation, tailoring, rendering, and approval remain unchanged.

## State Machine

Applications use `ApplicationState` from `app/domain/applications/enums.py`:

```text
DRAFT -> READY -> SUBMITTED -> VIEWED -> INTERVIEW -> OFFER -> ARCHIVED
  |       |          |           |          |           |
  |       |          |           |          |           +-> WITHDRAWN
  |       |          |           |          +-> ASSESSMENT
  |       |          |           +-> ASSESSMENT
  |       |          +-> REJECTED
  |       +-> WITHDRAWN
  +-> WITHDRAWN

REJECTED -> ARCHIVED
WITHDRAWN -> ARCHIVED
ARCHIVED is terminal
```

`ARCHIVED` is also allowed directly from all active states so users can close stale records without forcing artificial intermediate transitions.

Every transition is validated by `is_valid_transition()`. Invalid transitions raise `InvalidStateTransitionError`.

## Traceability

Each `JobApplication` stores:

- `recommendation_id`, `job_id`, `profile_id`
- `application_package_id` when created from an approval package
- `profile_version`
- `resume_path` and `cover_letter_path`
- `company_name` and `job_title`
- labels, lifecycle timestamps, and creation/update timestamps

`create_from_approved_package()` requires an `APPROVED` package, reads rendered document paths from `ApprovalService.get_documents()`, copies job metadata from the persisted job row, creates a draft application, and marks the recommendation as `applied`.

## Persistence

Migration `20260802_p11_create_application_tables.py` adds six tables:

| Table | Purpose |
|-------|---------|
| `applications` | Root tracked application record |
| `application_events` | Audit history for lifecycle and metadata actions |
| `application_notes` | User notes |
| `application_timeline_events` | Human-readable timeline |
| `application_reminders` | Follow-up reminders without external integrations |
| `application_outcomes` | Final outcome tracking |

Repositories live in `app/db/repositories/applications.py` and expose filtering by status, company, label, date range, pagination, search, and grouping for summaries.

## Service API

`ApplicationService` (`app/services/application_service.py`) supports:

- Creation: `create_application()`, `create_from_approved_package()`
- Lifecycle: `change_status()`, `archive()`
- Metadata: `update_application()`, `set_labels()`, `add_label()`, `remove_label()`
- Notes and timeline: `add_note()`, `list_notes()`, `add_timeline_event()`, `get_timeline()`, `get_history()`
- Reminders: `schedule_follow_up()`, `complete_reminder()`, `cancel_reminder()`, `snooze_reminder()`, `due_reminders()`
- Outcomes: `record_outcome()`, `get_outcome()`
- Reporting: `summarize()`, `analytics()`

Duplicate prevention raises `DuplicateApplicationError` when a non-closed application already exists for the same recommendation.

## Reminders

Reminder behavior is configured in `config/application.toml` and loaded by `ApplicationConfig`:

```toml
[reminders]
enabled = true
follow_up_default_days = 3

[labels]
default = []
```

The engine only stores and lists reminders. It does not send external notifications. Due reminder queries include both `pending` and `snoozed` reminders.

## CLI

```text
stagepilot application create --package-id <id>
stagepilot application list [--status] [--company] [--label] [--date-from] [--date-to]
stagepilot application show <id>
stagepilot application update <id> [--status] [--company] [--job-title] [--labels]
stagepilot application archive <id>
stagepilot application search <query>
stagepilot application summarize
stagepilot application analytics

stagepilot application reminder add <application-id> [--due-days] [--due-at]
stagepilot application reminder list [--status] [--due-before]
stagepilot application reminder complete <reminder-id>
stagepilot application reminder snooze <reminder-id> --due-at <iso-datetime>
```

## Analytics

`analytics()` returns:

- counts for total, submitted, viewed, interview, offer, rejected, withdrawn, active, and hired
- submission rate from total applications
- interview, offer, and rejection rates from submitted applications
- average response time in days from `submitted_at` to `responded_at`
- pipeline conversion percentages for submitted, viewed, interview, offer, and hired

Rejected applications count as submitted because they reached an employer-response terminal state.

## Tests

Application coverage includes domain transition tests, mocked service unit tests, CLI handler tests, and integration tests for the full lifecycle, approval-package creation, filtering/search, reminders, outcomes, summaries, analytics, and metadata updates.

Current verification baseline: `696 passed` and `ruff` clean.
