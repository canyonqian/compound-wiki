"""
Compound Wiki Memory Core v2.0
==============================

AI-driven automatic memory system for Agent conversations.

Core philosophy:
  - The AI Agent drives everything — not the human
  - Conversations automatically produce memory artifacts
  - Multiple Agents share one Wiki safely via concurrency control
  - Compound interest: every interaction grows the knowledge graph

Architecture:
  memory_core/
  ├── hook_engine.py     ← Conversation event hooks (on_message/on_response/on_turn_end)
  ├── extractor.py       ← LLM-powered fact/concept/decision/preference extraction
  ├── deduplicator.py    ← Near-duplicate detection + fact merge + supersede logic
  ├── shared_wiki.py     ← Concurrent-safe Wiki access (file locks / atomic writes)
  ├── agent_sdk.py       ← Universal adapter: Claude Code / Cursor / Copilot / OpenAI
  ├── memory_graph.py    ← Knowledge graph builder (entity relations / concept links)
  └── config.py          ← Memory-specific config (extraction rules / thresholds)

Usage:
  # In your Agent's conversation loop:
  from memory_core import MemoryCore
  
  mc = MemoryCore(wiki_path="./wiki", raw_path="./raw")
  
  # After each conversation turn:
  await mc.on_turn_end(user_message, assistant_response)
  # → Automatically extracts facts → Deduplicates → Writes to Wiki → Updates links

License: MIT
"""

__version__ = "2.0.0"
__author__ = "Compound Wiki Contributors"

from memory_core.hook_engine import HookEngine, HookEvent, HookResult
from memory_core.extractor import FactExtractor, ExtractionResult, FactType
from memory_core.deduplicator import Deduplicator, MergeAction
from memory_core.shared_wiki import SharedWiki, WikiTransaction
from memory_core.agent_sdk import MemoryCore, AgentConfig, AgentType, MemoryResult
from memory_core.memory_graph import MemoryGraph, GraphNode, GraphEdge
from memory_core.config import MemoryConfig

# Backward compatibility aliases
MemoryHook = HookEngine  # alias for convenience
AgentAdapter = MemoryCore  # alias: AgentAdapter is the integration point = MemoryCore

__all__ = [
    "MemoryCore",
    "HookEngine", "HookEvent", "HookResult", "MemoryHook",
    "FactExtractor", "ExtractionResult", "FactType",
    "Deduplicator", "MergeAction",
    "SharedWiki", "WikiTransaction",
    "AgentConfig", "AgentType", "AgentAdapter",
    "MemoryGraph", "GraphNode", "GraphEdge",
    "MemoryResult",
    "MemoryConfig",
]
