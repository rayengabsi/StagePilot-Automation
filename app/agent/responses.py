"""Response types for the StagePilot agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agent.intents import AgentIntent


@dataclass(frozen=True, slots=True)
class AgentResponse:
    """The structured result of one agent turn.

    ``message`` is the human-friendly text shown to the user. ``reasoning``
    explains what the agent did and why (the agent explains itself after
    every action). ``data`` carries the structured result for API/CLI
    consumers.
    """

    intent: AgentIntent
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    reasoning: tuple[str, ...] = ()
    success: bool = True
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise the response for CLI/API output."""
        return {
            "intent": self.intent.value,
            "message": self.message,
            "reasoning": list(self.reasoning),
            "data": self.data,
            "success": self.success,
            "error": self.error,
        }
