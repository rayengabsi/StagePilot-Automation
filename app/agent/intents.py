"""Intent model and deterministic classifier for the StagePilot agent.

Phase 1 classifies user messages deterministically (keyword based). The
classifier is intentionally simple and testable: it maps a message to exactly
one ``AgentIntent``. An optional LLM refinement step is deferred to a later
phase and will sit behind the same interface.
"""

from __future__ import annotations

import re
from enum import StrEnum


class AgentIntent(StrEnum):
    """The set of intents the Phase 1 agent can handle."""

    PROFILE_IMPORT = "profile_import"
    PROFILE_STATUS = "profile_status"
    PROFILE_EDIT = "profile_edit"
    DISCOVER = "discover"
    RECOMMEND = "recommend"
    LIST_RECOMMENDATIONS = "list_recommendations"
    AI_EXPLAIN = "ai_explain"
    PIPELINE = "pipeline"
    APPLICATION_ANALYTICS = "application_analytics"
    APPROVAL_QUEUE = "approval_queue"
    HELP = "help"
    UNKNOWN = "unknown"


#: Priority-ordered (intent, keyword tuples). The first intent whose any
#: keyword appears in the message wins. Ordering matters: more specific
#: intents must come before broader ones they overlap with.
_INTENT_PATTERNS: tuple[tuple[AgentIntent, tuple[str, ...]], ...] = (
    (
        AgentIntent.PROFILE_IMPORT,
        (
            "import resume",
            "import cv",
            "add my resume",
            "add resume",
            "new resume",
            "upload my cv",
            "upload resume",
            "upload cv",
            "importer",
            "import cv",
            "import ",
            "upload ",
            "ajoute mon cv",
        ),
    ),
    (
        AgentIntent.PIPELINE,
        (
            "pipeline",
            "run everything",
            "run all",
            "full run",
            "end-to-end",
            "complete pipeline",
            "executer tout",
        ),
    ),
    (
        AgentIntent.LIST_RECOMMENDATIONS,
        (
            "list recommendations",
            "my recommendations",
            "saved recommendations",
            "show recommendations",
            "existing recommendations",
            "persisted recommendations",
        ),
    ),
    (
        AgentIntent.RECOMMEND,
        (
            "recommend",
            "recommendation",
            "best jobs",
            "best match",
            "best matching",
            "top jobs",
            "suggest",
            "suggestion",
            "recommande",
            "classement",
            "top matches",
        ),
    ),
    (
        AgentIntent.DISCOVER,
        (
            "discover",
            "discovery",
            "find me jobs",
            "find jobs",
            "search jobs",
            "search for jobs",
            "new jobs",
            "new opportunities",
            "actualise",
            "update jobs",
            "find me",
            "find internships",
            "trouve",
            "cherche",
            "recherche",
            "jobs now",
        ),
    ),
    (
        AgentIntent.AI_EXPLAIN,
        (
            "explain",
            "explique",
            "pourquoi",
            "why this",
            "why does",
            "why is",
            "reason for",
        ),
    ),
    (
        AgentIntent.APPLICATION_ANALYTICS,
        (
            "applications",
            "application analytics",
            "analytics",
            "statistics",
            "statistiques",
            "candidatures",
            "outcomes",
            "follow-up",
            "follow up",
            "my progress",
            "progress",
            "how many applied",
            "application status",
        ),
    ),
    (
        AgentIntent.APPROVAL_QUEUE,
        (
            "approval",
            "approve",
            "approbation",
            "approval queue",
            "pending review",
            "file d'attente",
            "pending approvals",
        ),
    ),
    (
        AgentIntent.PROFILE_EDIT,
        (
            "edit profile",
            "update profile",
            "set summary",
            "set my summary",
            "modifier le profil",
            "--summary",
            "--name",
            "update my name",
        ),
    ),
    (
        AgentIntent.PROFILE_STATUS,
        (
            "profile",
            "profil",
            "who am i",
            "my info",
            "my details",
            "my summary",
            "status",
            "mon profil",
            "show profile",
            "career profile",
        ),
    ),
    (
        AgentIntent.HELP,
        (
            "what can you do",
            "how can you help",
            "list commands",
            "show commands",
            "what do you do",
            "can you help",
            "que peux-tu",
        ),
    ),
)

#: Short, exact greetings/help commands.
_HELP_EXACT: frozenset[str] = frozenset(
    {"help", "aide", "start", "/help", "/start", "hello", "bonjour", "hi"}
)


class IntentClassifier:
    """Deterministically map a user message to an AgentIntent.

    Phase 1 uses keyword matching only. The classifier is pure (no I/O), so it
    is trivially testable and safe to run before any model call.
    """

    def __init__(self) -> None:
        self._patterns = tuple(
            (intent, tuple(re.compile(re.escape(kw), re.IGNORECASE) for kw in keywords))
            for intent, keywords in _INTENT_PATTERNS
        )

    def classify(self, message: str) -> AgentIntent:
        """Return the best-matching intent for *message*."""
        if not message or not message.strip():
            return AgentIntent.UNKNOWN

        normalized = message.strip()
        if normalized.lower() in _HELP_EXACT:
            return AgentIntent.HELP

        for intent, regexes in self._patterns:
            for pattern in regexes:
                if pattern.search(normalized):
                    return intent
        return AgentIntent.UNKNOWN
