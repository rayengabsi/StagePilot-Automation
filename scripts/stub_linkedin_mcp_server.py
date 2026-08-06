"""Local stand-in for the real LinkedIn MCP server.

The real ``linkedin_mcp_server`` exposes ``search_jobs`` and
``get_job_details`` over stdio and returns *raw scraped text* (not structured
JSON) inside ``{url, sections: {...}}`` payloads:

- ``search_jobs``      -> ``{"url": ..., "sections": {"search_results": <text>}, "job_ids": [...]}``
- ``get_job_details``  -> ``{"url": ..., "sections": {"job_posting": <raw text>}}``

This stub mimics that exact protocol shape so ``LinkedInMCPConnector`` can be
exercised end-to-end without live LinkedIn credentials. It intentionally speaks
the real protocol (raw-text sections, numeric job ids) rather than the enriched
shape of the earlier fake.

Run it directly with::

    uv run python scripts/stub_linkedin_mcp_server.py [--expired]

Pass ``--expired`` to simulate an expired LinkedIn session (every tool returns a
login-required error) for exercising ``LinkedInSessionExpiredError``.
"""

from __future__ import annotations

import asyncio
import sys
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

_JOB_101 = {
    "id": "101",
    "url": "https://www.linkedin.com/jobs/view/101/",
    "posting": "\n".join(
        [
            "Tunis, Tunisia",
            "Software Engineer Intern (PFE)",
            "Acme Tech",
            "Remote # engineering",
            "About the job",
            "Final year project internship in backend engineering with Python and FastAPI.",
            "Responsibilities",
            "Build and ship backend microservices end to end.",
            "Requirements",
            "Python",
            "FastAPI",
            "REST APIs",
        ]
    ),
}

_JOB_102 = {
    "id": "102",
    "url": "https://www.linkedin.com/jobs/view/102/",
    "posting": "\n".join(
        [
            "Paris, France",
            "Data Science Apprenticeship",
            "Innova Labs",
            "On-site",
            "About the job",
            "Machine learning apprenticeship for computer science students.",
            "Requirements",
            "Machine Learning",
            "Python",
        ]
    ),
}

_ID_TO_JOB: dict[str, dict[str, str]] = {job["id"]: job for job in (_JOB_101, _JOB_102)}


def _expired() -> bool:
    return "--expired" in sys.argv


async def main() -> None:
    """Serve tools over stdio until the client disconnects."""
    server = Server(
        name="stub-linkedin-mcp-server",
        version="0.1.0",
        on_list_tools=_list_tools,
        on_call_tool=_call_tool,
    )
    async with stdio_server() as (read, write):
        await server.run(
            read,
            write,
            InitializationOptions(
                server_name="stub-linkedin-mcp-server",
                server_version="0.1.0",
                capabilities=ServerCapabilities(),
            ),
        )


async def _list_tools(_ctx: object, _params: object) -> ListToolsResult:
    """Advertise the tools in the same order as the real server."""
    return ListToolsResult(
        tools=[
            Tool(
                name="search_jobs",
                description="Search LinkedIn jobs and return matching job ids.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "keywords": {"type": "string"},
                        "location": {"type": "string"},
                        "job_type": {"type": "string"},
                        "max_pages": {"type": "integer"},
                    },
                },
            ),
            Tool(
                name="get_job_details",
                description="Fetch the raw text for a single LinkedIn job.",
                input_schema={
                    "type": "object",
                    "properties": {"job_id": {"type": "string"}},
                },
            ),
        ]
    )


async def _call_tool(_ctx: object, params: CallToolRequestParams) -> CallToolResult:
    """Route a call to the matching protocol stub handler."""
    if _expired():
        return _error("ERROR: Not logged in. Please log in to continue.")
    if params.name == "search_jobs":
        return _search(params.arguments or {})
    if params.name == "get_job_details":
        return _details(params.arguments or {})
    return _error(f"Unknown tool: {params.name}")


def _search(arguments: dict[str, Any]) -> CallToolResult:
    """Return job ids whose posting mentions every search keyword token."""
    keyword = str(arguments.get("keywords") or "").lower()
    tokens = [token for token in keyword.replace(",", " ").split() if token]
    job_ids: list[str] = []
    if tokens:
        for job in _ID_TO_JOB.values():
            if all(token in job["posting"].lower() for token in tokens):
                job_ids.append(job["id"])
    else:
        job_ids = list(_ID_TO_JOB)
    return _ok(
        {
            "url": "https://www.linkedin.com/jobs/",
            "sections": {"search_results": "Mocked search results.\n\n" + "\n".join(job_ids)},
            "job_ids": job_ids,
        }
    )


def _details(arguments: dict[str, Any]) -> CallToolResult:
    """Return the raw posting text for one job id."""
    job_id = str(arguments.get("job_id") or "")
    job = _ID_TO_JOB.get(job_id)
    if job is None:
        return _error(f"Job not found: {job_id}")
    return _ok(
        {
            "url": job["url"],
            "sections": {"job_posting": job["posting"]},
        }
    )


def _ok(payload: dict[str, Any]) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=str(payload))],
        structured_content=payload,
    )


def _error(message: str) -> CallToolResult:
    return CallToolResult(
        is_error=True,
        content=[TextContent(type="text", text=message)],
    )


if __name__ == "__main__":
    asyncio.run(main())
