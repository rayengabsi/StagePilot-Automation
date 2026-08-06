"""Synchronous adapter for a Model Context Protocol server over stdio.

The rest of StagePilot is synchronous, so this module wraps the ``async``
``mcp`` SDK with ``asyncio.run`` boundaries. Each top-level operation
(``list_tools`` / ``call_tool``) opens its own connection, initializes the
session, performs the request, and tears the transport down — the simplest
correct lifecycle for a periodic, stateless job search.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager, suppress
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult

__all__ = ["LinkedInMCPClient", "LinkedInMCPError"]


class LinkedInMCPError(RuntimeError):
    """Raised when an MCP interaction with the LinkedIn server fails."""


class LinkedInMCPClient:
    """Minimal synchronous MCP stdio client.

    Arguments:
        command: Path to the MCP server executable.
        args: Extra command-line arguments for the server process.
        env: Optional environment overrides merged over the current env.
        cwd: Working directory for the server process.
        timeout_seconds: Timeout for a single tool call.
    """

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        """Initialize the client with the server process parameters."""
        self._params = StdioServerParameters(
            command=command,
            args=list(args or []),
            env=env,
            cwd=cwd,
            encoding="utf-8",
            encoding_error_handler="replace",
        )
        self._timeout_seconds = timeout_seconds

    def list_tools(self) -> list[str]:
        """Return the names of the tools exposed by the server."""
        return asyncio.run(self._list_tools())

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> object:
        """Call an arbitrary server tool and return its parsed result."""
        return asyncio.run(self._call_tool(name, arguments))

    def call_many(self, calls: list[tuple[str, dict[str, Any] | None]]) -> list[object]:
        """Run several tool calls over one server session and return results.

        A single process is started, initialized, and used for all calls in
        the provided order, then torn down. This keeps the whole
        search → details → shutdown lifecycle on one connection.
        """
        return asyncio.run(self._call_many(calls))

    async def _call_many(self, calls: list[tuple[str, dict[str, Any] | None]]) -> list[object]:
        """Open one session and invoke each call sequentially."""
        try:
            async with self._open_session() as session:
                await session.initialize()
                results: list[object] = []
                for name, arguments in calls:
                    result = await session.call_tool(
                        name,
                        arguments,
                        read_timeout_seconds=self._timeout_seconds,
                    )
                    results.append(_parse_call_result(result))
                return results
        except Exception as exc:
            raise LinkedInMCPError(f"LinkedIn MCP tool call failed: {exc}") from exc

    async def _list_tools(self) -> list[str]:
        """Open a session and list the available tool names."""
        try:
            async with self._open_session() as session:
                result = await session.list_tools()
                return [tool.name for tool in result.tools]
        except Exception as exc:
            raise LinkedInMCPError(f"Failed to list LinkedIn MCP tools: {exc}") from exc

    async def _call_tool(self, name: str, arguments: dict[str, Any] | None) -> object:
        """Open a session and invoke the named tool."""
        try:
            async with self._open_session() as session:
                result = await session.call_tool(
                    name,
                    arguments,
                    read_timeout_seconds=self._timeout_seconds,
                )
        except Exception as exc:
            raise LinkedInMCPError(f"LinkedIn MCP tool call failed: {exc}") from exc
        return _parse_call_result(result)

    @asynccontextmanager
    async def _open_session(self) -> object:
        """Yield an initialized client session over the stdio transport."""
        async with (
            stdio_client(self._params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            yield session


def _parse_call_result(result: CallToolResult) -> object:
    """Convert an MCP tool result into plain Python data."""
    if bool(getattr(result, "is_error", False)):
        raise LinkedInMCPError(f"LinkedIn MCP tool returned an error: {_first_text(result)}")
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        return structured
    items = list(getattr(result, "content", []) or [])
    parsed = [_content_to_data(item) for item in items]
    parsed = [item for item in parsed if item is not None]
    if len(parsed) == 1:
        return parsed[0]
    return parsed


def _content_to_data(item: object) -> object:
    """Return a plain value for a single content item."""
    text: object = getattr(item, "text", None)
    if text is not None and isinstance(text, str):
        return _maybe_json(text)
    return None


def _first_text(result: CallToolResult) -> str:
    """Return the first text payload from a result for error messages."""
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if isinstance(text, str) and text:
            return text
    return str(result)


def _maybe_json(value: str) -> object:
    """Try to parse a text payload as JSON; otherwise return the raw string."""
    with suppress(ValueError):
        return json.loads(value)
    return value
