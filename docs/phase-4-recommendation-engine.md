# Phase 4: Recommendation Engine

## Overview

Phase 4 delivers the **Recommendation Engine** — a deterministic, rule-based pipeline that matches a candidate's master profile against all hard-filter-approved jobs, scores each match across 8 similarity categories, aggregates scores into a weighted final score, ranks jobs by fit, and persists all recommendations to the database for auditability.

The engine processes jobs through four stages:

| Stage | Component | Responsibility |
|---|---|---|
| **Profile Loading** | `RecommendationService` | Load the current `MasterProfile` and all hard-filter-approved jobs from the database |
| **Hard Rule Gate** | `HardRuleMatcher` | Reject jobs that fail mandatory constraints (country, work mode, language) before any scoring |
| **Similarity Scoring** | `SimilarityScorer` | Compute per-category similarity scores (0–100) across 8 categories using fuzzy string matching |
| **Score Aggregation** | `ScoreAggregator` | Combine per-category scores into a single weighted final score using configurable weights from `matching.toml` |

The engine is **purely deterministic** — no AI models, no LLM calls, no external APIs. Every scoring rule is hand-crafted keyword matching with `rapidfuzz` partial-ratio support.

---

## Architecture

The Recommendation Engine follows the same Clean Architecture layering as the rest of the project:

```
app/domain/recommendation/          <-- Domain layer: frozen dataclass entities, enums, error types, matcher, scorer, aggregator
app/services/recommendation_service.py  <-- Application service: orchestrates the full pipeline
app/db/models/recommendation.py     <-- Persistence: 2 SQLAlchemy ORM models
app/config/matching.toml            <-- Configuration: weights, thresholds, hard-rule toggles, fuzz threshold
app/config/matching.py              <-- Runtime: MatchingConfig frozen dataclass + TOML loader
app/cli/commands.py                 <-- CLI: 2 new subcommands (recommend, feedback)
```

### Layer Responsibilities

| Layer | Directory | Role |
|---|---|---|
| **Domain** | `app/domain/recommendation/` | Pure dataclasses with no dependencies on frameworks or databases. All entities are `frozen=True, slots=True`. Domain enums (`RecommendationStatus`, `FeedbackReason`, `HardRule`) define closed sets of valid values. Domain errors (`RecommendationError`, `ProfileNotReadyError`, `RecommendationValidationError`) provide typed exception hierarchy. Domain logic (`HardRuleMatcher`, `SimilarityScorer`, `ScoreAggregator`, `ProfileMatcher`) contains all business rules. |
| **Services** | `app/services/recommendation_service.py` | Orchestration layer. `RecommendationService` loads profile+qualified jobs, runs `ProfileMatcher` per job, ranks results, persists recommendations, and provides feedback management. |
| **Persistence** | `app/db/models/recommendation.py` | SQLAlchemy ORM models mapped to 2 MySQL tables: `recommendations` and `recommendation_feedback`. |
| **Configuration** | `app/config/matching.toml` + `app/config/matching.py` | TOML-driven configuration with no hardcoded weights. `MatchingConfig` frozen dataclass loaded at runtime with `lru_cache`. |
| **CLI** | `app/cli/commands.py` | Two subcommands: `stagepilot recommend` and `stagepilot feedback`. |

---

## Matching Pipeline Walkthrough

The full pipeline flows through these stages for each job:

```
RecommendationService.recommend()
    |
    v
1. _load_profile()
    |   Queries the current MasterProfile via ProfileService
    |   Queries the single profiles row for profile_id
    |   Raises ProfileNotReadyError if no profile exists
    v
MasterProfile + profile_id
    |
    v
2. _load_jobs()
    |   SELECT jobs WHERE id IN (
    |       SELECT job_id FROM job_matches WHERE hard_filter_ok = TRUE
    |   )
    |   Only jobs that passed Phase 2 hard filters are candidates
    v
List[Job] (qualified candidates)
    |
    v
3. For each job:
    |
    +---> ProfileMatcher.match(profile, job, profile_id)
    |       |
    |       +---> HardRuleMatcher.evaluate(profile, job)
    |       |       |   Checks country, work mode, language
    |       |       |   Returns HardRuleResult(passed=True/False, reasons=[])
    |       |       v
    |       |   If NOT passed:
    |       |       Return Recommendation(status=REJECTED, final_score=0.0)
    |       |
    |       +---> SimilarityScorer.score_all(profile, job)
    |       |       |   Computes 8 per-category scores (0-100 each)
    |       |       v
    |       |   ScoreBreakdown(skills, technologies, education, ...)
    |       |
    |       +---> SimilarityScorer.match_detail(profile, job)
    |       |       |   Computes matched/missing lists for skills, technologies, preferences
    |       |       v
    |       |   MatchedDetail(matched_skills, missing_skills, ...)
    |       |
    |       +---> ScoreAggregator.aggregate(ScoreBreakdown)
    |       |       |   Weighted sum using config weights from matching.toml
    |       |       v
    |       |   final_score (float, 0-100)
    |       |
    |       +---> Compare final_score >= recommendation_cutoff threshold
    |       |       YES to RecommendationStatus.ACTIVE
    |       |       NO  to RecommendationStatus.REJECTED
    |       |
    |       +---> Return Recommendation (frozen dataclass)
    |
    v
4. Sort by final_score descending, assign ranking_position
    |
    v
5. _persist_recommendations()
    |   Batch-insert all Recommendations into the recommendations table
    v
6. Return ranked list (optionally truncated to top_n)
```

---

## Weight System

All scoring weights are defined in `matching.toml` and loaded into the `MatchingConfig` frozen dataclass at runtime. There are **no hardcoded weights** in any Python source file.

### Default Weights

| Category | Weight | Rationale |
|---|---|---|
| `skills` | 35.0 | Skills are the strongest signal of job fit |
| `technologies` | 20.0 | Technology stack experience is highly relevant |
| `education` | 10.0 | Field of study and degree level |
| `experience` | 10.0 | Job title and company relevance |
| `languages` | 5.0 | Spoken language match |
| `projects` | 5.0 | Project relevance |
| `location` | 10.0 | Geographic proximity |
| `preferences` | 5.0 | Preferred technologies and language |

The weights sum to 100.0 by default, but the `ScoreAggregator` normalizes by the actual sum of weights, so custom configurations that sum to any value work correctly.

### Thresholds

| Threshold | Default | Purpose |
|---|---|---|
| `minimum_score` | 0.0 | Reserved for future use; currently all non-rejected scores pass |
| `recommendation_cutoff` | 30.0 | Minimum `final_score` for a job to be marked `ACTIVE`; below this threshold the recommendation is `REJECTED` |

### Fuzz Threshold

| Setting | Default | Purpose |
|---|---|---|
| `fuzz_threshold` | 60 | Minimum `rapidfuzz` partial ratio for fuzzy string matching (0-100) |

### How to Customize

Edit `matching.toml` and re-run. The config is loaded on every command invocation via `get_matching_config()` (cached with `lru_cache(maxsize=1)` per process):

```toml
[weights]
skills = 35.0
technologies = 20.0
education = 10.0
experience = 10.0
languages = 5.0
projects = 5.0
location = 10.0
preferences = 5.0

[thresholds]
minimum_score = 0.0
recommendation_cutoff = 30.0

[hard_rules]
match_country = true
match_work_mode = true
match_language = true

[similarity]
fuzz_threshold = 60
```

---

## Hard Rules

Hard rules act as a mandatory gate before any similarity scoring. Each rule is independently toggleable in `matching.toml` under the `[hard_rules]` section.

### Rule: `match_country`

- **Toggle:** `hard_rules.match_country` (default `true`)
- **Logic:** If the profile has preferred countries and the job has a location, check if any preferred country name appears (case-insensitive) in the job location string.
- **Failure reason:** `"Job location "{location}" does not match preferred countries: {countries}"`

### Rule: `match_work_mode`

- **Toggle:** `hard_rules.match_work_mode` (default `true`)
- **Logic:**
  - If `RemotePreference.ANY` to always passes
  - If `RemotePreference.REMOTE` to job text must contain a remote keyword (`remote`, `teletravail`, `work from home`, `distantiel`)
  - If `RemotePreference.ONSITE` to job text must NOT contain remote keywords (`remote`, `teletravail`, `work from home`)
- **Failure reasons:** `"Job does not appear to support remote work"` or `"Job is remote but profile prefers onsite"`

### Rule: `match_language`

- **Toggle:** `hard_rules.match_language` (default `true`)
- **Logic:** If the profile has a preferred language, the job text must mention it (case-insensitive substring match).
- **Failure reason:** `"Job does not mention preferred language "{language}"`

If any hard rule fails, the recommendation is immediately assigned `status=REJECTED`, `final_score=0.0`, and all score breakdown fields are set to `0.0`. The rejection reasons are stored as a JSON array in the `hard_rule_reasons` column.

---

## Similarity Scoring

The `SimilarityScorer` computes 8 per-category scores, each normalized to 0-100. All text matching uses `rapidfuzz.fuzz.ratio` with the configurable `fuzz_threshold` (default 60) for fuzzy matching, with an exact substring check as a fast path.

### 1. Skills Score

Considers all profile skills plus technologies from experience and project entries. Each skill/technology is looked up in the job text via fuzzy match.

```
matched = count of skills/techs found in job text
total   = len(profile.skills) + sum(exp.technologies) + sum(proj.technologies)
score   = (matched / total) * 100    (0 if total == 0)
```

### 2. Technologies Score

Only considers technologies from experience and project entries (deduplicated).

```
all_techs = set(exp.technologies + proj.technologies)
matched   = count of techs found in job text
score     = (matched / len(all_techs)) * 100    (0 if empty)
```

### 3. Education Score

Each education entry contributes up to 100 points:

| Match | Points |
|---|---|
| `field_of_study` found in job text | +40 |
| `degree` found in job text | +40 |
| `institution` found in job text | +20 |

```
score = min(sum / len(education), 100.0)    (0 if no education)
```

### 4. Experience Score

Each experience entry contributes up to 100 points:

| Match | Points |
|---|---|
| `title` found in job text | +50 |
| `company` found in job text | +30 |
| `description` (first 100 chars) found in job text | +20 |

```
score = min(sum / len(experience), 100.0)    (0 if no experience)
```

### 5. Languages Score

```
matched = count of profile languages found in job text
score   = (matched / len(languages)) * 100    (50.0 if no languages to neutral)
```

Returns 50.0 (neutral) when the profile has no language entries, avoiding a penalty for missing data.

### 6. Projects Score

Each project entry contributes up to 100 points:

| Match | Points |
|---|---|
| `name` found in job text | +50 |
| `description` (first 100 chars) found in job text | +50 |

```
score = min(sum / len(projects), 100.0)    (0 if no projects)
```

### 7. Location Score

| Condition | Score |
|---|---|
| Job location is empty | 50.0 (neutral) |
| Profile location is empty | 50.0 (neutral) |
| Direct location match (substring) | 100.0 |
| Preferred country matches job location | 80.0 |
| Preferred city matches job location | 80.0 |
| Partial region match | 60.0 |
| No match | 0.0 |

### 8. Preferences Score

Examines preferred technologies and preferred language from the profile preferences:

```
prefs_list = preferred_technologies + [preferred_language]
matched    = count of prefs found in job text
score      = (matched / len(prefs_list)) * 100    (100.0 if empty to neutral)
```

### Match Detail

The `SimilarityScorer.match_detail()` method computes matched/missing lists for three categories:

- **Skills:** Matched skills vs. missing skills (from profile skills + experience techs + project techs)
- **Technologies:** Matched technologies vs. missing technologies (from experience + projects only)
- **Preferences:** Matched preferences vs. unmatched preferences

These are stored as JSON arrays in the `recommendations` table for full auditability.

---

## Score Aggregation

The `ScoreAggregator` combines the 8 per-category scores into a single `final_score` using the configurable weights from `matching.toml`:

```
final_score = (
    skills_score       * skills_weight       +
    technologies_score * technologies_weight  +
    education_score    * education_weight     +
    experience_score   * experience_weight    +
    languages_score    * languages_weight     +
    projects_score     * projects_weight      +
    location_score     * location_weight      +
    preferences_score  * preferences_weight
) / sum_of_all_weights
```

The result is a float in the 0-100 range representing overall job fit.

---

## Recommendation Schema

The `Recommendation` domain entity and `RecommendationRecord` ORM model store the full output of the matching pipeline.

### DB Columns (10 categories)

| Column | Type | Source |
|---|---|---|
| `id` | INT (PK, auto) | Auto-generated |
| `profile_id` | INT (FK to profiles.id) | From profile loading |
| `job_id` | INT (FK to jobs.id) | From qualified jobs query |
| `final_score` | FLOAT | Output of `ScoreAggregator.aggregate()` |
| `ranking_position` | INT | Position after score-sorted ranking |
| `status` | VARCHAR(20) | `active`, `rejected`, `applied`, `archived` |
| `matched_skills_json` | JSON | List of matched skill names |
| `missing_skills_json` | JSON | List of missing skill names |
| `matched_technologies_json` | JSON | List of matched technologies |
| `missing_technologies_json` | JSON | List of missing technologies |
| `matched_preferences_json` | JSON | List of matched preferences |
| `unmatched_preferences_json` | JSON | List of unmatched preferences |
| `score_breakdown_json` | JSON | Dict of 8 category to score |
| `hard_rule_passed` | BOOLEAN | Whether hard rules passed |
| `hard_rule_reasons` | JSON | Array of failure reason strings |
| `created_at` | DATETIME | Server-default `now()` |

### JSON Breakdown

The `score_breakdown_json` column stores a flat dictionary:

```json
{
  "skills": 85.0,
  "technologies": 70.0,
  "education": 60.0,
  "experience": 100.0,
  "languages": 50.0,
  "projects": 0.0,
  "location": 100.0,
  "preferences": 100.0
}
```

### Matched/Missing Items

The `matched_skills_json` and `missing_skills_json` columns make it immediately obvious what a candidate is qualified for and where they fall short:

```json
{
  "matched_skills": ["Python", "Docker", "SQL", "Git"],
  "missing_skills": ["Kubernetes", "AWS", "Terraform"],
  "matched_technologies": ["Python", "PostgreSQL"],
  "missing_technologies": ["Redis", "GraphQL"],
  "matched_preferences": ["Python"],
  "unmatched_preferences": ["Go"]
}
```

---

## Feedback Model

The `RecommendationFeedback` domain entity and `RecommendationFeedbackRecord` ORM model support user feedback on individual recommendations.

### Predefined Reasons

| Enum Value | Description |
|---|---|
| `wrong_country` | Job is in a country the candidate does not want |
| `wrong_field` | Job is outside the candidate's field/industry |
| `wrong_technologies` | Job uses technologies the candidate does not work with |
| `too_senior` | Job requires more experience than the candidate has |
| `salary` | Salary does not meet expectations |
| `not_remote` | Job does not offer remote work |
| `other` | Catch-all for custom reasons |

### Feedback Table

| Column | Type | Notes |
|---|---|---|
| `id` | INT (PK, auto) | Auto-generated |
| `recommendation_id` | INT (FK to recommendations.id) | Indexed |
| `reason` | VARCHAR(50) | One of the 7 predefined reasons |
| `comment` | TEXT | Optional free-text comment |
| `created_at` | DATETIME | Server-default `now()` |

Feedback is persisted immediately via the service layer and linked to the parent recommendation.

---

## CLI

Two new subcommands are available under the `stagepilot` root.

### `stagepilot recommend [--top N] [--json] [--list]`

Run the recommendation engine against all hard-filter-approved jobs.

```bash
# Run recommendations, see a formatted table
uv run stagepilot recommend

# Limit to top 5 recommendations
uv run stagepilot recommend --top 5

# Output raw JSON (useful for scripting)
uv run stagepilot recommend --json

# List previously persisted recommendations (no re-run)
uv run stagepilot recommend --list

# List top 10 persisted recommendations as JSON
uv run stagepilot recommend --list --top 10 --json
```

**Table output format:**

```
Rank   Score    Job ID   Status       Matched Skills
------------------------------------------------------------------------------
1      82.3     45       active       Python, Docker, SQL, Git, AWS...
2      65.7     32       active       Python, SQL, Flask...
3      45.0     78       active       Java, Spring...
4      28.5     12       rejected     ...
```

**JSON output format:**

```json
[
  {
    "profile_id": 1,
    "job_id": 45,
    "final_score": 82.3,
    "ranking_position": 1,
    "status": "active",
    "matched_detail": {
      "matched_skills": ["Python", "Docker", "SQL", "Git"],
      "missing_skills": ["Kubernetes", "AWS"],
      "matched_technologies": ["Python", "PostgreSQL"],
      "missing_technologies": ["Redis"],
      "matched_preferences": ["Python"],
      "unmatched_preferences": []
    },
    "score_breakdown": {
      "skills": 85.0,
      "technologies": 70.0,
      "education": 60.0,
      "experience": 100.0,
      "languages": 50.0,
      "projects": 0.0,
      "location": 100.0,
      "preferences": 100.0
    },
    "hard_rule_passed": true,
    "hard_rule_reasons": [],
    "created_at": "2026-07-30 20:00:00+00:00"
  }
]
```

### `stagepilot feedback <recommendation_id> --reason <reason> [--comment <text>]`

Submit feedback for a specific recommendation.

```bash
# Submit feedback with a reason only
uv run stagepilot feedback 5 --reason wrong_country

# Submit feedback with a reason and a comment
uv run stagepilot feedback 12 --reason wrong_technologies --comment "Uses Java but I only work with Python"
```

**Available reasons:** `wrong_country`, `wrong_field`, `wrong_technologies`, `too_senior`, `salary`, `not_remote`, `other`

**Output:**

```json
{
  "recommendation_id": 12,
  "reason": "wrong_technologies",
  "comment": "Uses Java but I only work with Python",
  "created_at": "2026-07-30 20:05:00+00:00"
}
```

---

## Configuration

All matching configuration lives in a single TOML file: `app/config/matching.toml`.

### Structure

```toml
[weights]
skills = 35.0
technologies = 20.0
education = 10.0
experience = 10.0
languages = 5.0
projects = 5.0
location = 10.0
preferences = 5.0

[thresholds]
minimum_score = 0.0
recommendation_cutoff = 30.0

[hard_rules]
match_country = true
match_work_mode = true
match_language = true

[similarity]
fuzz_threshold = 60
```

### Configuration Loading

The `MatchingConfig` frozen dataclass is defined in `app/config/matching.py`:

```python
@dataclass(frozen=True, slots=True)
class MatchingConfig:
    weights: dict[str, float]
    thresholds: dict[str, float]
    hard_rules: dict[str, bool]
    fuzz_threshold: int

    @classmethod
    def load(cls, path: Path = MATCHING_CONFIG_PATH) -> MatchingConfig: ...

@lru_cache(maxsize=1)
def get_matching_config(path: Path = MATCHING_CONFIG_PATH) -> MatchingConfig: ...
```

All scoring and matching components receive the config via dependency injection in their constructors. No Python file hardcodes a weight or threshold.

### Adding New Config Sections

To add a new configurable parameter:
1. Add it to `matching.toml` under the appropriate section
2. Add the field to `MatchingConfig` in `matching.py`
3. Update the `load()` method to parse the new field
4. Inject `MatchingConfig` into any component that needs it

---

## Future AI Integration Point

The Recommendation Engine is explicitly designed to support future AI/LLM augmentation without requiring architectural changes.

### Structured Explanations Enable NL Generation

Every recommendation contains structured data that can feed an AI prompt:

```
Given this structured recommendation:
- Final score: 82.3
- Score breakdown: {skills: 85, technologies: 70, education: 60, ...}
- Matched skills: [Python, Docker, SQL, Git]
- Missing skills: [Kubernetes, AWS]
- Hard rules: passed

Generate a natural-language explanation of why this job is a good fit.
```

The stored `score_breakdown_json` and matched/missing detail columns provide all the signals an LLM needs to produce human-readable reasoning without any additional computation.

### Integration Points

| Integration | How It Would Work | What Already Exists |
|---|---|---|
| **NL Explanations** | LLM generates a `reasoning_text` column from structured breakdown | Full score breakdown + matched/missing items persisted |
| **Adaptive Weights** | LLM suggests weight adjustments based on feedback patterns | All weights are in config, not hardcoded |
| **Smart Cutoff** | LLM sets per-job cutoff thresholds | `recommendation_cutoff` is already configurable |
| **Feedback Loop** | LLM analyzes feedback trends to improve recommendations | Full feedback history in `recommendation_feedback` table |

### Extending for AI

The schema already has space for AI-generated data. To add AI explanations:

1. Add a `reasoning_text` column to the `recommendations` table
2. Add an optional `ai_provider` column to track which model generated the explanation
3. Inject an LLM client into `ProfileMatcher` or `RecommendationService`
4. The LLM receives the structured `Recommendation` dataclass and returns natural language

No existing code paths would need to change -- AI would be an additive layer.

---

## Database Schema

Two new tables are created by the Alembic migration `0a0463c97286_create_recommendation_tables.py`.

### `recommendations`

```sql
CREATE TABLE recommendations (
    id                          INT PRIMARY KEY AUTO_INCREMENT,
    profile_id                  INT NOT NULL,
    job_id                      INT NOT NULL,
    final_score                 FLOAT NOT NULL,
    ranking_position            INT NOT NULL,
    status                      VARCHAR(20) NOT NULL DEFAULT 'active',
    matched_skills_json         JSON,
    missing_skills_json         JSON,
    matched_technologies_json   JSON,
    missing_technologies_json   JSON,
    matched_preferences_json    JSON,
    unmatched_preferences_json  JSON,
    score_breakdown_json        JSON,
    hard_rule_passed            BOOLEAN NOT NULL,
    hard_rule_reasons           JSON,
    created_at                  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id)    REFERENCES profiles(id),
    FOREIGN KEY (job_id)        REFERENCES jobs(id),
    INDEX (profile_id),
    INDEX (job_id)
);
```

- 16 columns total
- 6 JSON columns for structured scoring data
- Foreign keys to `profiles` and `jobs` tables
- Indexed on both foreign keys

### `recommendation_feedback`

```sql
CREATE TABLE recommendation_feedback (
    id                  INT PRIMARY KEY AUTO_INCREMENT,
    recommendation_id   INT NOT NULL,
    reason              VARCHAR(50) NOT NULL,
    comment             TEXT,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (recommendation_id) REFERENCES recommendations(id),
    INDEX (recommendation_id)
);
```

- 5 columns total
- Foreign key to `recommendations` with cascade support via SQLAlchemy relationship
- Indexed on `recommendation_id`

---

## Architecture Diagram

```
+-----------------------------------------------------------------------+
|                       Recommendation Engine                           |
+-----------------------------------------------------------------------+
|                                                                       |
|  +---------------------------+    +--------------------------------+  |
|  |   RecommendationService   |    |        MatchingConfig          |  |
|  |   (services/)            |--->|        (config/matching.toml)  |  |
|  +-------------+-------------+    +--------------------------------+  |
|                |                                                      |
|                | ProfileMatcher (domain/recommendation/profile_matcher.py)
|                |                                                      |
|                +--------------------------------------------------+  |
|                |                                                      |
|                v                                                      |
|  +-------------------------+    +--------------------------+          |
|  |    HardRuleMatcher      |    |    SimilarityScorer     |          |
|  |    (matcher.py)         |    |    (scorer.py)          |          |
|  |                         |    |                         |          |
|  |  - match_country        |    |  - skills (35%)        |          |
|  |  - match_work_mode      |    |  - technologies (20%)  |          |
|  |  - match_language       |    |  - education (10%)     |          |
|  +------------+------------+    |  - experience (10%)    |          |
|               |                 |  - languages (5%)      |          |
|               | (rejected)      |  - projects (5%)       |          |
|               v                 |  - location (10%)      |          |
|  +-------------------------+    |  - preferences (5%)    |          |
|  |    HardRuleResult       |    +------------+----------+          |
|  |    passed=false         |                 |                     |
|  |    reasons=[...]        |                 | ScoreBreakdown      |
|  +-------------------------+                 v                     |
|                              +--------------------------+          |
|                              |     ScoreAggregator      |          |
|                              |     (aggregator.py)      |          |
|                              |                          |          |
|                              |  weighted_sum(           |          |
|                              |    breakdown,            |          |
|                              |    weights               |          |
|                              |  ) / total_weight        |          |
|                              +------------+-------------+          |
|                                           |                        |
|                                           v final_score            |
|                              +--------------------------+          |
|                              |      Recommendation      |          |
|                              |      (domain entity)     |          |
|                              |                          |          |
|                              |  - final_score           |          |
|                              |  - ranking_position      |          |
|                              |  - status                |          |
|                              |  - score_breakdown       |          |
|                              |  - matched_detail        |          |
|                              |  - hard_rule_result      |          |
|                              +------------+-------------+          |
|                                           |                        |
|                                           v persist               |
|                              +--------------------------+          |
|                              |  RecommendationRecord    |          |
|                              |  (db/models/             |          |
|                              |   recommendation.py)     |          |
|                              +--------------------------+          |
|                                                                       |
+-----------------------------------------------------------------------+

Data Sources:
+----------------+    +----------------------+    +----------------------+
| MasterProfile  |    |  Job (qualified)     |    |   MatchingConfig     |
| (Phase 3)      |    |  (Phase 1+2)         |    |   (matching.toml)    |
+----------------+    +----------------------+    +----------------------+

Persistence:
+--------------------+    +----------------------------+
|  recommendations   |    |  recommendation_feedback   |
+--------------------+    +----------------------------+
```

---

## Design Decisions

### No AI -- Purely Deterministic Rule-Based Matching

The entire engine uses hand-crafted fuzzy matching, keyword lists, and weighted aggregation. There is no machine learning, no LLM API call, and no external NLP service. This is deliberate for the same reasons as Phase 3:

- **Reproducibility** -- Same profile + same jobs = same recommendations every time.
- **Speed** -- Matching completes in milliseconds per job, no GPU or network access needed.
- **Debuggability** -- Every score can be traced to a specific fuzzy match or keyword hit.
- **Zero cost** -- No API tokens, no model hosting, no usage limits.

**Trade-off:** Rule-based matching cannot understand semantic similarity the way an LLM can. "Python developer" and "software engineer (Python)" would not match via simple keyword scoring. Future AI augmentation is designed to be additive (see Future AI Integration Point).

### Clean Architecture

The Recommendation Engine follows strict Clean Architecture boundaries:

| Layer | Dependencies | Can Import From |
|---|---|---|
| **Domain** (entities.py, enums.py, errors.py, matcher.py, scorer.py, aggregator.py, profile_matcher.py) | Python stdlib + rapidfuzz + MatchingConfig | Domain layer only + config |
| **Services** (recommendation_service.py) | Domain + DB models | Domain + Persistence |
| **Persistence** (recommendation.py ORM models) | SQLAlchemy | SQLAlchemy |
| **CLI** (commands.py) | Services | All layers |

### Frozen Dataclasses for Domain Entities

All domain entities (`HardRuleResult`, `ScoreBreakdown`, `MatchedDetail`, `Recommendation`, `RecommendationFeedback`) are:

- **`frozen=True`** -- Immutable after creation. Prevents accidental mutation.
- **`slots=True`** -- Reduces memory overhead by avoiding `__dict__`.

### TOML-Driven Configuration

All tunable parameters live in `matching.toml`. No weights, thresholds, or toggles are hardcoded in Python. This allows:

- **Experimentation** -- Change weights and re-run without code changes.
- **Transparency** -- Non-developers can read and adjust settings.
- **Version control** -- Config changes are tracked in git alongside code.

### Integration with Phase 2 Hard Filters

The recommendation engine only considers jobs that passed Phase 2 hard filtering. The `_load_jobs()` method runs:

```sql
SELECT * FROM jobs WHERE id IN (
    SELECT job_id FROM job_matches WHERE hard_filter_ok = TRUE
)
```

This means the Recommendation Engine is the **third layer** of a three-layer filtering pipeline:
1. **Phase 2 Hard Filters** -- PFE, location, seniority, CS field, employment type
2. **Phase 4 Hard Rules** -- Country, work mode, language
3. **Phase 4 Similarity Scoring** -- Weighted category scoring

### Auditable Persistence

Every recommendation decision is persisted to the `recommendations` table. No recommendation is calculated in memory only. This enables:

- **Historical analysis** -- Review past recommendations and their scores.
- **Feedback correlation** -- Link user feedback to specific scoring breakdowns.
- **Trend tracking** -- See how recommendations change as the profile or job corpus evolves.

---

## Future Directions

- Add AI-powered natural language explanations for each recommendation
- Implement adaptive weight tuning based on feedback patterns
- Add batch feedback processing (`stagepilot feedback --bulk`)
- Expose recommendation statistics (`stagepilot recommend --stats`)
- Add recommendation acceptance flow (`stagepilot recommend --accept <id>`)
- Implement automated feedback-driven weight recalibration
- Add per-job cutoff thresholds for more granular control
- Support multiple profile matching (compare against multiple candidates)
- Add export recommendations to CSV/JSON for external analysis
