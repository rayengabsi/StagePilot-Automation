"""LinkedIn MCP server integration for StagePilot.

The LinkedIn MCP adapter lets StagePilot use a Model Context Protocol
server as a job provider. Milestone 1 ships the thin synchronous client
and the ``LinkedInMCPConnector`` that feeds LinkedIn results into the
existing discovery pipeline.
"""

from __future__ import annotations

from app.infrastructure.linkedin_mcp.client import LinkedInMCPClient, LinkedInMCPError

__all__ = ["LinkedInMCPClient", "LinkedInMCPError"]
