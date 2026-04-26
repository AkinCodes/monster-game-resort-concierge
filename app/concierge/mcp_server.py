"""
MCP (Model Context Protocol) Server
====================================

Exposes the Monster Game Resort Concierge's tools via the MCP standard,
allowing any MCP-compatible agent or client to discover and call them.

Tools are dynamically read from the ToolRegistry — single source of truth.
No hardcoded tool list. Add a tool to the registry and it automatically
appears in MCP.

Usage:
    # Import and mount in your FastAPI app
    mcp = MCPServer(tool_registry=registry)
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _openai_to_mcp_schema(openai_schema: dict) -> dict:
    """Convert an OpenAI function-calling schema to MCP tool format."""
    fn = openai_schema.get("function", openai_schema)
    return {
        "name": fn.get("name", ""),
        "description": fn.get("description", ""),
        "inputSchema": fn.get("parameters", {"type": "object", "properties": {}}),
    }


@dataclass
class MCPServer:
    """Lightweight MCP-compatible tool server.

    Implements the core MCP tool discovery and execution protocol
    without requiring the full MCP SDK. Compatible with any client
    that speaks the MCP JSON-RPC protocol over stdio or HTTP.

    Tools are read dynamically from the ToolRegistry — no hardcoded
    tool list. Single source of truth prevents drift.
    """

    tool_registry: Any  # ToolRegistry instance from tools.py
    server_name: str = "monster-resort-concierge"
    server_version: str = "1.0.0"

    def list_tools(self) -> List[dict]:
        """MCP tools/list — dynamically read from the registry."""
        mcp_tools = []
        for tool in self.tool_registry.list():
            schema = tool.to_openai_schema()
            if schema:
                mcp_tools.append(_openai_to_mcp_schema(schema))
        return mcp_tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> dict:
        """MCP tools/call — execute a tool and return structured result."""
        request_id = str(uuid.uuid4())[:8]
        tool = self.tool_registry.get(name)

        if not tool:
            logger.warning(
                "mcp_unknown_tool",
                extra={"tool": name, "request_id": request_id},
            )
            return {
                "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                "isError": True,
            }

        t0 = time.perf_counter()
        try:
            result = await self.tool_registry.async_execute_with_timing(
                name, request_id=request_id, **arguments
            )
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)

            logger.info(
                "mcp_tool_call_ok",
                extra={
                    "tool": name,
                    "request_id": request_id,
                    "latency_ms": latency_ms,
                },
            )

            # Return structured content — no double-serialization
            return {
                "content": [{"type": "json", "json": result}],
                "isError": False,
            }

        except Exception as exc:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.error(
                "mcp_tool_call_failed",
                extra={
                    "tool": name,
                    "request_id": request_id,
                    "latency_ms": latency_ms,
                    "error_type": type(exc).__name__,
                },
            )
            # Structured error — no raw exception message leaked to client
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Tool '{name}' failed. Request ID: {request_id}",
                    }
                ],
                "isError": True,
            }

    async def handle_jsonrpc(self, request: dict) -> dict:
        """Handle a single MCP JSON-RPC request."""
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {
                        "name": self.server_name,
                        "version": self.server_version,
                    },
                },
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": self.list_tools()},
            }

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = await self.call_tool(tool_name, arguments)
            return {"jsonrpc": "2.0", "id": req_id, "result": result}

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

    def get_server_info(self) -> dict:
        """Return MCP server metadata for discovery endpoints."""
        tools = self.list_tools()
        return {
            "name": self.server_name,
            "version": self.server_version,
            "protocol": "MCP",
            "protocolVersion": "2024-11-05",
            "tools": [t["name"] for t in tools],
            "tool_count": len(tools),
            "description": "Monster Game Resort Concierge tool server — "
            "book rooms, retrieve bookings, search resort amenities.",
        }


# ==========================================================================
# STUDY NOTES — What was refactored and why
# ==========================================================================
#
# An external code reviewer flagged 4 issues. Here's what we fixed
# and what we deliberately left alone.
#
# ── FIXED ─────────────────────────────────────────────────────────────────
#
# 1. SINGLE SOURCE OF TRUTH (was: hardcoded MCP_TOOLS list)
#
#    BEFORE: A 45-line MCP_TOOLS list duplicated every tool's schema.
#    The ToolRegistry in tools.py ALSO defined schemas via to_openai_schema().
#    Two places describing the same tools = guaranteed drift.
#
#    AFTER: list_tools() dynamically reads from self.tool_registry.list(),
#    converts each tool's OpenAI schema to MCP format via _openai_to_mcp_schema().
#    Add a tool to the registry → it automatically appears in MCP. Zero drift.
#
#    WHY IT MATTERS: In production, a tool listed in MCP but missing from
#    the registry would cause call_tool() to return "Unknown tool" — a bug
#    that's invisible until a client actually calls it.
#
#
# 2. STRUCTURED ERROR HANDLING (was: leaking raw exception messages)
#
#    BEFORE: except Exception as e: return {"text": f"Tool execution failed: {e}"}
#    This leaks internal stack details to any client calling the MCP server.
#
#    AFTER: The error response says "Tool 'X' failed. Request ID: abc123"
#    with no internal details. The actual error type is logged server-side
#    with the request_id for correlation.
#
#    WHY IT MATTERS: Error messages in APIs should help the CLIENT retry
#    or report the issue, not expose your internals. The request_id lets
#    you find the real error in logs.
#
#
# 3. NO DOUBLE-SERIALIZATION (was: json.dumps(result) inside text content)
#
#    BEFORE: {"type": "text", "text": json.dumps(result, default=str)}
#    The client receives a JSON response containing a string that is ALSO JSON.
#    To use the data, they must: parse the outer JSON, extract the text field,
#    then parse THAT string as JSON again. Two parse steps.
#
#    AFTER: {"type": "json", "json": result}
#    The result object is embedded directly. One parse. Cleaner for tool
#    chaining where the output of one tool feeds into another.
#
#    WHY IT MATTERS: default=str silently converts datetimes, enums, and
#    custom objects to lossy strings. Direct embedding preserves types.
#
#
# 4. REQUEST ID + LATENCY IN LOGS (was: just tool name and error string)
#
#    BEFORE: logger.error("mcp_tool_call_failed", extra={"tool": name, "error": str(e)})
#    No way to correlate a client's error report with server logs.
#    No latency data for performance debugging.
#
#    AFTER: Every call gets a request_id (uuid4[:8]). Both success and
#    failure paths log: tool name, request_id, latency_ms, and (on failure)
#    error_type. The client receives the request_id in error responses.
#
#    WHY IT MATTERS: In multi-agent systems, a client might chain 5 tool
#    calls. When one fails, the request_id is the only way to find the
#    right log entry among thousands.
#
#
# ── LEFT ALONE (acceptable for portfolio) ─────────────────────────────────
#
# - Protocol version "2024-11-05": This IS the real MCP spec version from
#   Anthropic. Not a placeholder. Clients that hard-match it will work.
#
# - No cancellation handling: If a client disconnects mid-tool-execution,
#   the tool runs to completion anyway. In production you'd use
#   asyncio.shield() or task cancellation. Overkill here.
#   INTERVIEW NOTE: mention this as a known limitation.
#
# - default=str removed (was in json.dumps): Now that we return structured
#   JSON directly, this is no longer relevant. But if we ever need to
#   serialize complex objects, a custom JSONEncoder would be the right fix.
#
# - No security filtering on tools: Tools are statically registered at
#   startup via make_registry(). There's no dynamic tool loading, so
#   there's nothing to filter. If tools were user-supplied or loaded from
#   a database, you'd want schema validation + sandboxing before execution.
#
# ==========================================================================
