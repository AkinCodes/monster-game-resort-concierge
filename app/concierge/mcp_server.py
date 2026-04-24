"""
MCP (Model Context Protocol) Server
====================================

Exposes the Monster Game Resort Concierge's tools via the MCP standard,
allowing any MCP-compatible agent or client to discover and call them.

Runs alongside the existing custom ToolRegistry -- both interfaces
serve the same underlying tool functions.

Usage:
    python -m app.core.mcp_server          # standalone MCP server on stdio
    # Or import create_mcp_app() and mount in your FastAPI app
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Tool definitions (MCP-compatible JSON Schema) ────────────────────────

VALID_HOTELS = [
    "The Mummy Resort & Tomb-Service",
    "The Werewolf Lodge: Moon & Moor",
    "Castle Frankenstein: High Voltage Luxury",
    "Vampire Manor: Eternal Night Inn",
    "Zombie Bed & Breakfast: Bites & Beds",
    "Ghostly B&B: Spectral Stay",
]

MCP_TOOLS = [
    {
        "name": "book_room",
        "description": "Book a room at one of our official Monster Resort properties.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Guest session ID"},
                "guest_name": {"type": "string", "description": "Guest full name"},
                "hotel_name": {
                    "type": "string",
                    "description": "Resort property name",
                    "enum": VALID_HOTELS,
                },
                "room_type": {"type": "string", "description": "Room category"},
                "check_in": {"type": "string", "description": "Check-in date (YYYY-MM-DD)"},
                "check_out": {"type": "string", "description": "Check-out date (YYYY-MM-DD)"},
            },
            "required": ["session_id", "guest_name", "hotel_name", "room_type", "check_in", "check_out"],
        },
    },
    {
        "name": "get_booking",
        "description": "Retrieve details for an existing booking by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "booking_id": {"type": "string", "description": "The booking ID to look up"},
            },
            "required": ["booking_id"],
        },
    },
    {
        "name": "search_amenities",
        "description": "Search the resort knowledge base for amenities, activities, and hotel information.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query about resort amenities or services"},
            },
            "required": ["query"],
        },
    },
]


@dataclass
class MCPServer:
    """Lightweight MCP-compatible tool server.

    Implements the core MCP tool discovery and execution protocol
    without requiring the full MCP SDK. Compatible with any client
    that speaks the MCP JSON-RPC protocol over stdio or HTTP.
    """

    tool_registry: Any  # ToolRegistry instance from tools.py
    server_name: str = "monster-resort-concierge"
    server_version: str = "1.0.0"

    def list_tools(self) -> List[dict]:
        """MCP tools/list — return available tools with JSON Schema."""
        return MCP_TOOLS

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> dict:
        """MCP tools/call — execute a tool and return the result."""
        tool = self.tool_registry.get(name)
        if not tool:
            return {
                "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                "isError": True,
            }

        try:
            result = await self.tool_registry.async_execute_with_timing(name, **arguments)
            return {
                "content": [{"type": "text", "text": json.dumps(result, default=str)}],
                "isError": False,
            }
        except Exception as e:
            logger.error("mcp_tool_call_failed", extra={"tool": name, "error": str(e)})
            return {
                "content": [{"type": "text", "text": f"Tool execution failed: {e}"}],
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
        return {
            "name": self.server_name,
            "version": self.server_version,
            "protocol": "MCP",
            "protocolVersion": "2024-11-05",
            "tools": [t["name"] for t in MCP_TOOLS],
            "description": "Monster Game Resort Concierge tool server — "
            "book rooms, retrieve bookings, search resort amenities.",
        }
