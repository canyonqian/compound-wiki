"""
Output Adapters
================

Adapters sync Wiki content to external display/editing systems.

Available Adapters:
  • Obsidian — Sync wiki/ to Obsidian vault (bidirectional)
  • Logseq — Export to Logseq graph format  
  • Web UI — Optional lightweight dashboard
"""

from .base import BaseAdapter
from .obsidian import ObsidianAdapter
from .logseq import LogseqAdapter
from .web_ui import WebDashboardAdapter

__all__ = [
    "BaseAdapter",
    "ObsidianAdapter", 
    "LogseqAdapter",
    "WebDashboardAdapter",
]
