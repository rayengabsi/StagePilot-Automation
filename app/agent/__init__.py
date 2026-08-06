"""StagePilot v2 agent layer.

Phase 1 introduces ``CareerAgent``: the first agent-layer class that
orchestrates the existing StagePilot services without changing them.
"""

from __future__ import annotations

from app.agent.agent import CareerAgent
from app.agent.intents import AgentIntent, IntentClassifier
from app.agent.responses import AgentResponse

__all__ = ["AgentIntent", "AgentResponse", "CareerAgent", "IntentClassifier"]
