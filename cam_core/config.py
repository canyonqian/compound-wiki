"""
Memory Core Configuration
==========================

Tunable parameters for automatic memory extraction and management.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class ExtractionRules:
    """Controls what gets extracted from conversations."""

    # Fact types to extract (all enabled by default)
    extract_facts: bool = True  # "User prefers dark mode"
    extract_concepts: bool = True  # "Microservices architecture pattern"
    extract_decisions: bool = True  # "Chose Redis over Memcached for caching"
    extract_preferences: bool = True  # "Hates verbose documentation style"
    extract_tasks: bool = True  # "Need to implement auth middleware"
    extract_entities: bool = True  # People, projects, tools mentioned

    # Quality thresholds
    min_confidence: float = 0.6  # Minimum LLM confidence to accept a fact
    min_fact_length: int = 10  # Ignore very short extractions
    max_fact_length: int = 500  # Truncate very long facts

    # Rule-based pre-filter (before LLM call)
    min_exchange_length: int = 15  # Skip very short exchanges
    min_signal_count: int = 1  # Min signal patterns for extraction

    # Extraction triggers
    extract_on_every_turn: bool = False  # Extract on every message (expensive)
    extract_on_long_turn: bool = True  # Extract when turn > N tokens
    long_turn_threshold: int = 500  # Token threshold for "long turn"
    extract_on_explicit_save: bool = True  # User says "remember this" etc.

    # Batch control
    max_extractions_per_turn: int = 10  # Cap extractions per conversation turn
    batch_queue_size: int = 20  # Queue before forced flush


@dataclass
class DedupConfig:
    """Controls duplicate detection and merging."""

    # Similarity thresholds
    exact_match_threshold: float = 0.95  # Above this = same fact (skip)
    near_duplicate_threshold: float = 0.8  # 0.8-0.95 = merge/supersede
    merge_threshold: float = 0.7  # 0.7-0.8 = related but keep both

    # Semantic similarity method: "embedding" | "tfidf" | "keyword"
    similarity_method: str = "keyword"  # Default: keyword overlap (no API needed)

    # Supersede behavior
    auto_supersede: bool = True  # Auto-mark old as superseded by new
    keep_superseded_history: bool = True  # Don't delete, mark with timestamp

    # Conflict resolution for multi-agent
    conflict_strategy: str = "latest_wins"  # "latest_wins" | "merge" | "manual"


@dataclass
class ConcurrencyConfig:
    """Controls concurrent access for multi-Agent scenarios."""

    enable_locking: bool = True  # File-based locking for Wiki writes
    lock_timeout_seconds: float = 30.0  # Max wait for lock acquisition
    lock_retry_interval: float = 0.5  # Retry interval if locked

    # Write strategy
    atomic_writes: bool = True  # Write to temp + rename (crash-safe)
    backup_before_write: bool = True  # Keep .bak before overwrite
    max_backups: int = 5  # Rotate backups

    # Multi-agent identity
    agent_id: str = "default-agent"  # Each Agent gets a unique ID
    track_agent_contributions: bool = True  # Record which Agent wrote what


@dataclass
class GraphConfig:
    """Knowledge graph construction settings."""

    auto_link_entities: bool = True  # Auto-detect entity mentions → links
    auto_link_concepts: bool = True  # Auto-link related concepts
    max_links_per_page: int = 20  # Don't over-link
    link_strength_threshold: float = 0.5  # Min relevance for auto-link

    # Graph export
    export_mermaid: bool = True  # Generate Mermaid diagrams in pages
    export_json: bool = True  # Export graph as JSON for visualization


@dataclass
class MemoryConfig:
    """Master configuration for Memory Core."""

    # Paths (resolved relative to project root)
    wiki_path: str = "./wiki"
    raw_path: str = "./raw"
    state_path: str = "./.cam_core/state"
    graph_path: str = "./.cam_core/graph"

    # Sub-configs
    extraction: ExtractionRules = field(default_factory=ExtractionRules)
    deduplication: DedupConfig = field(default_factory=DedupConfig)
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    graph: GraphConfig = field(default_factory=GraphConfig)

    # LLM settings for extraction
    llm_provider: str = "auto"  # "auto" | "openai" | "anthropic" | "ollama"
    llm_model: str = "auto"  # "auto" = use whatever is available
    llm_temperature: float = 0.1  # Low temp for factual extraction

    # Logging
    log_level: str = "INFO"
    log_extraction: bool = True  # Log every extraction decision
    quiet_mode: bool = False  # Suppress non-error output

    @classmethod
    def from_file(cls, path: str) -> "MemoryConfig":
        """Load config from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryConfig":
        """Create config from dictionary."""
        cfg = cls()

        if "wiki_path" in data:
            cfg.wiki_path = data["wiki_path"]
        if "raw_path" in data:
            cfg.raw_path = data["raw_path"]
        if "llm_provider" in data:
            cfg.llm_provider = data["llm_provider"]
        if "llm_model" in data:
            cfg.llm_model = data["llm_model"]

        if "extraction" in data:
            for k, v in data["extraction"].items():
                if hasattr(cfg.extraction, k):
                    setattr(cfg.extraction, k, v)

        if "deduplication" in data:
            for k, v in data["deduplication"].items():
                if hasattr(cfg.deduplication, k):
                    setattr(cfg.deduplication, k, v)

        if "concurrency" in data:
            for k, v in data["concurrency"].items():
                if hasattr(cfg.concurrency, k):
                    setattr(cfg.concurrency, k, v)

        if "graph" in data:
            for k, v in data["graph"].items():
                if hasattr(cfg.graph, k):
                    setattr(cfg.graph, k, v)

        return cfg

    def to_dict(self) -> Dict[str, Any]:
        """Export config as dictionary."""
        return {
            "wiki_path": self.wiki_path,
            "raw_path": self.raw_path,
            "state_path": self.state_path,
            "graph_path": self.graph_path,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "llm_temperature": self.llm_temperature,
            "log_level": self.log_level,
            "log_extraction": self.log_extraction,
            "quiet_mode": self.quiet_mode,
            "extraction": self.extraction.__dict__,
            "deduplication": self.deduplication.__dict__,
            "concurrency": self.concurrency.__dict__,
            "graph": self.graph.__dict__,
        }

    def save(self, path: str) -> None:
        """Save config to JSON file."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


# Default config instance
DEFAULT_CONFIG = MemoryConfig()
