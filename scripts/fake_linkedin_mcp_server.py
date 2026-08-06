"""Fake LinkedIn MCP server used to verify StagePilot's MCP adapter.

This is a *local stand-in* for a real LinkedIn MCP server. It exposes a
``search_roles`` tool over stdio and returns a fixed set of sample roles so
that ``LinkedInMCPConnector`` can be exercised end-to-end without live
LinkedIn credentials. Run it with:

    uv run python scripts/fake_linkedin_mcp_server.py
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server.lowlevel import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    ServerCapabilities,
    TextContent,
    Tool,
)

TOOL_NAME = "search_roles"

_SAMPLE_ROLES: list[dict[str, Any]] = [
    {
        "id": "MOCK-101",
        "title": "Software Engineer Intern (PFE)",
        "company_name": "Acme Tech",
        "url": "https://www.linkedin.com/jobs/view/mock-101",
        "location": "Tunis, Tunisia",
        "description": "Final year project internship in backend engineering with Python.",
        "employmentType": "INTERNSHIP",
        "remoteStatus": "hybrid",
    },
    {
        "id": "MOCK-102",
        "title": "Data Science Apprenticeship",
        "company_name": "Innova Labs",
        "url": "https://www.linkedin.com/jobs/view/mock-102",
        "location": "Paris, Île-de-France, France",
        "description": "Machine learning apprenticeship for computer science students.",
        "employment_type": "APPRENTICESHIP",
        "remoteStatus": "On-site",
    },
]


async def main() -> None:
    """Read tools from stdio, serve them, and exit."""
    server = Server(
        name="fake-linkedin-mcp-server",
        version="0.1.0",
        on_list_tools=_list_tools,
        on_call_tool=_call_tool,
    )
    async with stdio_server() as (read, write):
        await server.run(
            read,
            write,
            InitializationOptions(
                server_name="fake-linkedin-mcp-server",
                server_version="0.1.0",
                capabilities=ServerCapabilities(),
            ),
        )


async def _list_tools(_ctx: object, _params: object) -> ListToolsResult:
    """Advertise the search tool."""
    return ListToolsResult(
        tools=[
            Tool(
                name=TOOL_NAME,
                description=(
                    "Search LinkedIn for roles matching keyword, location and type filters."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "keywords": {"type": "string"},
                        "location": {"type": "string"},
                        "job_type": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                },
            )
        ]
    )


async def _call_tool(_ctx: object, params: CallToolRequestParams) -> CallToolResult:
    """Respond to a search invocation with the sample roles."""
    if params.name != TOOL_NAME:
        return _error(f"Unknown tool: {params.name}")
    arguments = params.arguments or {}
    limit = int(arguments.get("limit") or 10)
    keyword = str(arguments.get("keywords") or "").lower()
    roles = _SAMPLE_ROLES
    if keyword:
        roles = [
            role
            for role in roles
            if keyword in role["title"].lower()
            or keyword in str(role.get("description", "")).lower()
        ]
    roles = roles[:limit]
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps({"jobs": roles}))],
        structured_content={"jobs": roles},
    )


def _error(message: str) -> CallToolResult:
    """Return an error tool result."""
    return CallToolResult(
        is_error=True,
        content=[TextContent(type="text", text=json.dumps({"error": message}))],
    )


if __name__ == "__main__":
    asyncio.run(main())
