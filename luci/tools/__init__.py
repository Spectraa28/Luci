"""All of Luci's tools wired into one registry.

Flagship: calendar, notes, messages, search
Luci-specific: learning journal, application tracker, outreach drafter
Self-management: manage_memory, update_soul, create_skill
Optional: apple tools, MCP servers, experimental
"""

from __future__ import annotations

import os
import sqlite3

from luci.config import Settings
from luci.tools import applications, calendar, learning, memory_admin, message, notes, outreach, search
from luci.tools.registry import ToolRegistry


def build_registry(conn: sqlite3.Connection, settings: Settings, memory=None) -> ToolRegistry:
    registry = ToolRegistry()

    # ── Flagship tools (inherited from waku) ─────────────────────────────────
    registry.register(calendar.make_tool(
        conn, settings.home,
        apple_calendar=settings.apple_calendar,
        google_calendar=settings.google_calendar,
        google_credentials=settings.google_calendar_credentials,
    ))
    registry.register(calendar.make_list_tool(conn))
    registry.register(notes.make_tool(conn))
    registry.register(message.make_tool(settings.home))
    registry.register(search.make_tool())

    # ── Luci-specific tools ───────────────────────────────────────────────────
    registry.register(learning.make_log_tool(conn))
    registry.register(learning.make_search_tool(conn))
    registry.register(applications.make_track_tool(conn))
    registry.register(applications.make_list_tool(conn))
    registry.register(outreach.make_tool(conn))

    # ── Memory self-management ────────────────────────────────────────────────
    if memory is not None:
        registry.register(memory_admin.make_manage_memory_tool(memory))
        registry.register(memory_admin.make_update_soul_tool(settings))
        registry.register(memory_admin.make_create_skill_tool(settings, memory))

    # ── Experimental (opt-in) ─────────────────────────────────────────────────
    if os.getenv("LUCI_EXPERIMENTAL", "") in ("1", "true", "yes"):
        from luci.tools import experimental
        for t in experimental.make_tools():
            registry.register(t)

    # ── Apple ecosystem (opt-in, macOS only) ──────────────────────────────────
    if settings.apple_tools:
        from luci.tools import apple
        for t in apple.make_tools():
            registry.register(t)

    # ── MCP servers (opt-in via .luci/mcp.json) ───────────────────────────────
    mcp_config = settings.home / "mcp.json"
    if mcp_config.exists():
        try:
            from luci.tools.mcp_client import MCPBridge
            bridge = MCPBridge(mcp_config)
            for t in bridge.start():
                registry.register(t)
            registry.mcp_bridge = bridge
        except ImportError:
            print("mcp.json found but the 'mcp' package is missing — pip install 'luci[mcp]'")

    return registry
