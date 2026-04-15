"""
CAM — Auto Engine
============================
Intelligent automation layer for CAM.

Modules:
  - config.py    : Configuration management (paths, API keys, model settings)
  - state.py     : State persistence (processed files, operation history, stats)
  - watcher.py   : File system monitor (auto-detects new files in raw/)
  - pipeline.py  : Ingestion engine (raw → LLM → wiki pages + links)
  - collector.py : Web content fetcher (URLs/RSS/bookmarks → raw/)
  - scheduler.py : Cron-like task scheduler (auto LINT, summaries, reports)
  - agent.py     : Main entry point & CLI interface

Quick Start:
  pip install watchdog anthropic openai  # optional deps
  python auto/agent.py init              # first-time setup
  python auto/agent.py start             # full auto mode
"""

from .config import load_config, generate_default_config, CompoundWikiConfig
from .state import StateManager, WikiState
from .pipeline import IngestionPipeline, LLMClient
from .collector import WebCollector
from .watcher import FileWatcher
from .scheduler import TaskScheduler

__version__ = "1.0.0"
__all__ = [
    "CompoundWikiConfig",
    "StateManager", "WikiState",
    "IngestionPipeline", "LLMClient",
    "WebCollector",
    "FileWatcher",
    "TaskScheduler",
    "load_config", "generate_default_config",
]
