"""Bundled Hermes slash command list for the TUI command palette."""

from __future__ import annotations

HERMES_COMMANDS: list[dict] = [
    # session
    {"command": "/new", "category": "session", "description": "Start a new conversation"},
    {"command": "/clear", "category": "session", "description": "Clear conversation history"},
    {"command": "/history", "category": "session", "description": "Show conversation history"},
    {"command": "/save", "category": "session", "description": "Save conversation to file"},
    {"command": "/retry", "category": "session", "description": "Retry the last message"},
    {"command": "/stop", "category": "session", "description": "Stop the current agent turn"},
    {"command": "/undo", "category": "session", "description": "Undo last message"},
    {"command": "/compress", "category": "session", "description": "Compress conversation context"},
    {"command": "/rollback", "category": "session", "description": "Rollback to a previous state"},
    {"command": "/snapshot", "category": "session", "description": "Take a session snapshot"},
    {"command": "/background", "category": "session", "description": "Move task to background"},
    {"command": "/resume", "category": "session", "description": "Resume a background task"},
    {"command": "/agents", "category": "session", "description": "List active agents"},
    {"command": "/queue", "category": "session", "description": "Show task queue"},
    {"command": "/goal", "category": "session", "description": "Set or show current goal"},
    {"command": "/steer", "category": "session", "description": "Steer the current agent"},
    # config
    {"command": "/model", "category": "config", "description": "Switch model"},
    {"command": "/personality", "category": "config", "description": "Change personality/skin"},
    {"command": "/verbose", "category": "config", "description": "Toggle verbose output"},
    {"command": "/fast", "category": "config", "description": "Toggle fast mode"},
    {"command": "/reasoning", "category": "config", "description": "Toggle extended reasoning"},
    {"command": "/yolo", "category": "config", "description": "Toggle yolo (no confirmation) mode"},
    {"command": "/skin", "category": "config", "description": "Change UI skin"},
    {"command": "/voice", "category": "config", "description": "Toggle voice output"},
    {"command": "/statusbar", "category": "config", "description": "Toggle status bar"},
    {"command": "/indicator", "category": "config", "description": "Set progress indicator style"},
    # tools
    {"command": "/tools", "category": "tools", "description": "List available tools"},
    {"command": "/toolsets", "category": "tools", "description": "Manage toolsets"},
    {"command": "/browser", "category": "tools", "description": "Open browser tool"},
    {"command": "/skills", "category": "tools", "description": "List installed skills"},
    {"command": "/reload-mcp", "category": "tools", "description": "Reload MCP servers"},
    {"command": "/reload", "category": "tools", "description": "Reload configuration"},
    {"command": "/cron", "category": "tools", "description": "Manage scheduled tasks"},
    {"command": "/kanban", "category": "tools", "description": "Show kanban board"},
    {"command": "/curator", "category": "tools", "description": "Open memory curator"},
    # info
    {"command": "/help", "category": "info", "description": "Show help"},
    {"command": "/usage", "category": "info", "description": "Show token/cost usage"},
    {"command": "/insights", "category": "info", "description": "Show conversation insights"},
    {"command": "/platforms", "category": "info", "description": "Show connected platforms"},
    {"command": "/paste", "category": "info", "description": "Paste from clipboard"},
    {"command": "/copy", "category": "info", "description": "Copy last response"},
    {"command": "/debug", "category": "info", "description": "Show debug info"},
    {"command": "/profile", "category": "info", "description": "Show flavor profile"},
]


def filter_commands(prefix: str) -> list[dict]:
    """Return commands matching the typed prefix (after the leading /)."""
    needle = prefix.lstrip("/").lower()
    if not needle:
        return HERMES_COMMANDS
    return [c for c in HERMES_COMMANDS if c["command"].lstrip("/").startswith(needle)]
