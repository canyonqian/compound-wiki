"""
CAM Core — Automatic Memory Engine
=====================================

Three-layer Wiki architecture:
  entity/    — People, projects, tools, preferences
  concept/   — Ideas, patterns, technologies
  synthesis/ — Decisions, cross-entity insights

Components:
  extractor.py       — LLM-powered fact/concept/decision/preference extraction
  deduplicator.py    — Near-duplicate detection + fact merge
  shared_wiki.py     — Concurrent-safe Wiki access (file locks / atomic writes)
  memory_graph.py    — Knowledge graph builder (auto entity/concept linking)
  config.py          — Memory-specific config (extraction rules / thresholds)
"""

__version__ = "2.0.0"
__author__ = "CAM Contributors"

from cam_core.extractor import FactExtractor, ExtractionResult, FactType
from cam_core.deduplicator import Deduplicator, MergeAction
from cam_core.shared_wiki import SharedWiki, WikiTransaction
from cam_core.memory_graph import MemoryGraph, GraphNode, GraphEdge
from cam_core.config import MemoryConfig

__all__ = [
    "FactExtractor",
    "ExtractionResult",
    "FactType",
    "Deduplicator",
    "MergeAction",
    "SharedWiki",
    "WikiTransaction",
    "MemoryGraph",
    "GraphNode",
    "GraphEdge",
    "MemoryConfig",
]
