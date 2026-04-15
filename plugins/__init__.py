"""
CAM Plugin System
============================

Plugin-based architecture for data ingestion and integration.
Supports: MCP Server, Browser Extension, Obsidian, CLI, API, Bot, Email, etc.

Architecture:
    plugins/
    ├── __init__.py          # Package init & registry
    ├── base.py              # Abstract plugin interface
    ├── mcp_server.py        # MCP Protocol Server
    ├── sources/             # Data source plugins
    │   ├── __init__.py
    │   ├── api_source.py    # REST API endpoint
    │   ├── browser.py       # Browser extension / bookmarklet
    │   ├── clipboard.py     # System clipboard monitor
    │   ├── email.py         # IMAP email watcher
    │   ├── rss.py           # RSS/Atom feed reader
    │   ├── bot.py           # Telegram/Discord/WeChat bot
    │   └── file_watch.py    # File system watcher (enhanced)
    └── adapters/            # Output / display adapters
        ├── __init__.py
        ├── obsidian.py      # Obsidian vault sync
        ├── logseq.py        # Logseq graph support
        └── web_ui.py        # Web dashboard (optional)

Usage:
    from plugins import CamMCP, SourceRegistry
    
    # Start MCP server for AI tools
    server = CamMCP()
    server.run()
    
    # Register custom source
    registry = SourceRegistry()
    registry.register("my_custom", MyCustomSource())
"""

from .base import (
    BaseSource,
    BaseAdapter,
    IngestItem,
    IngestResult,
    SourceConfig,
)
from .mcp_server import server as _mcp_server, run_mcp_server
from .sources import SourceRegistry, get_all_sources

# Backward-compatible alias: CamMCP wraps the server
class CamMCP:
    """Wrapper around the MCP server instance."""
    def __init__(self):
        self._server = _mcp_server
    
    def run(self, transport="stdio"):
        run_mcp_server(transport)

__all__ = [
    "BaseSource",
    "BaseAdapter",
    "IngestItem",
    "IngestResult",
    "SourceConfig",
    "CamMCP",
    "SourceRegistry",
    "get_all_sources",
    "run_mcp_server",
]
