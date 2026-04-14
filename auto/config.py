"""
Compound Wiki - Configuration System
=====================================
Manages all configuration: paths, API keys, model settings, automation rules.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ── Default paths ──────────────────────────────────────────────
DEFAULT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RAW_DIR = DEFAULT_ROOT / "raw"
DEFAULT_WIKI_DIR = DEFAULT_ROOT / "wiki"
DEFAULT_OUTPUTS_DIR = DEFAULT_ROOT / "outputs"
DEFAULT_SCHEMA_DIR = DEFAULT_ROOT / "schema"
DEFAULT_CONFIG_FILE = DEFAULT_ROOT / "auto" / "config.json"


@dataclass
class LLMConfig:
    """LLM provider configuration."""

    # Provider: openai, anthropic, ollama, azure_openai, etc.
    provider: str = "anthropic"

    # API credentials (loaded from env or config file)
    api_key: str = ""
    base_url: str = ""

    # Model selection per task type
    models: dict[str, str] = field(default_factory=lambda: {
        "ingest": "claude-sonnet-4-20250514",
        "query":  "claude-haiku-4-20250514",
        "lint":   "claude-sonnet-4-20250514",
        "collect": "claude-haiku-4-20250514",
    })

    # Generation parameters
    max_tokens: int = 8192
    temperature: float = 0.3

    def get_model(self, task: str) -> str:
        return self.models.get(task, self.models.get("ingest", "claude-sonnet-4-20250514"))


@dataclass
class WatcherConfig:
    """File watcher settings."""

    enabled: bool = True

    # Directories to watch
    watch_directories: list[str] = field(default_factory=lambda: ["raw"])

    # File patterns to process
    file_patterns: list[str] = field(default_factory=lambda: [
        "*.md", "*.txt", "*.rst", "*.adoc",
        "*.html", "*.htm",
        "*.json", "*.csv",
        "*.py", ".js", ".ts",
    ])

    # Patterns to ignore
    ignore_patterns: list[str] = field(default_factory=lambda: [
        ".DS_Store", "Thumbs.db", "~*", "*.tmp", "*.swp",
        ".gitkeep",
    ])

    # Debounce: wait N seconds after last change before processing
    debounce_seconds: float = 3.0

    # Auto-ingest when new file detected
    auto_ingest: bool = True

    # Batch mode: wait for N seconds of quiet before batch-processing all new files
    batch_mode: bool = True
    batch_wait_seconds: float = 30.0


@dataclass
class SchedulerConfig:
    """Scheduler / cron settings."""

    enabled: bool = true if sys.platform != "win32" else False

    # Scheduled tasks
    tasks: dict[str, dict] = field(default_factory=lambda: {
        "daily_lint": {
            "schedule": "0 8 * * *",       # Every day at 08:00
            "action": "lint",
            "enabled": True,
            "description": "Daily wiki health check & fix",
        },
        "weekly_summary": {
            "schedule": "0 20 * * 0",      # Every Sunday at 20:00
            "action": "summary",
            "enabled": True,
            "description": "Weekly knowledge growth summary",
        },
        "monthly_report": {
            "schedule": "0 9 1 * *",       # 1st of each month at 09:00
            "action": "report",
            "enabled": False,
            "description": "Monthly compound report",
        },
    })


@dataclass
class CollectorConfig:
    """Web collector settings."""

    enabled: bool = True

    # Output directory for collected content
    output_dir: str = "raw/collected"

    # Request settings
    timeout_seconds: int = 30
    max_content_length: int = 5 * 1024 * 1024  # 5MB

    # Content extraction preferences
    extract_main_content: bool = True
    strip_ads: bool = True
    convert_to_markdown: bool = True

    # Rate limiting
    requests_per_minute: int = 10

    # User agent
    user_agent: str = "CompoundWiki-Bot/1.0 (Educational Research)"


@dataclass
class PipelineConfig:
    """Ingestion pipeline settings."""

    # Max files to process in one batch
    max_files_per_batch: int = 10

    # Max file size to process (bytes) — skip large binaries
    max_file_size_bytes: int = 2 * 1024 * 1024  # 2MB

    # Whether to auto-create synthesis pages from query answers
    auto_archive_queries: bool = True

    # LINT after every N ingestions
    lint_every_n_ingests: int = 10

    # Whether to send notification on completion
    notify_on_complete: bool = False
    notification_command: str = ""


@dataclass
class CompoundWikiConfig:
    """Top-level configuration."""

    # Paths
    root_dir: Path = field(default_factory=lambda: DEFAULT_ROOT)
    raw_dir: Path = field(default_factory=lambda: DEFAULT_RAW_DIR)
    wiki_dir: Path = field(default_factory=lambda: DEFAULT_WIKI_DIR)
    outputs_dir: Path = field(default_factory=lambda: DEFAULT_OUTPUTS_DIR)
    schema_dir: Path = field(default_factory=lambda: DEFAULT_SCHEMA_DIR)

    # Sub-modules
    llm: LLMConfig = field(default_factory=LLMConfig)
    watcher: WatcherConfig = field(default_factory=WatcherConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    collector: CollectorConfig = field(default_factory=CollectorConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)

    # Logging
    log_level: str = "INFO"
    log_file: str = "auto/logs/compound-wiki.log"

    # Schema rule file path (CLAUDE.md or AGENTS.md)
    rule_file: str = "schema/CLAUDE.md"

    # Persist state between runs
    state_file: str = "auto/state/state.json"


def _resolve_env_vars(obj):
    """Recursively resolve ${ENV_VAR} references in strings."""
    import re

    if isinstance(obj, str):
        def _replace_env(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))
        return re.sub(r'\$\{(\w+)\}', _replace_env, obj)
    elif isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_env_vars(item) for item in obj]
    return obj


def load_config(config_path: Optional[Path | str] = None) -> CompoundWikiConfig:
    """
    Load configuration from file, falling back to defaults.
    
    Priority: config file > environment variables > defaults
    """
    cfg = CompoundWikiConfig()

    # Determine config file location
    if config_path is None:
        config_path = DEFAULT_CONFIG_FILE
    config_path = Path(config_path)

    # Load from JSON if exists
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            raw_data = _resolve_env_vars(raw_data)

            # Map top-level keys
            if "llm" in raw_data and isinstance(raw_data["llm"], dict):
                cfg.llm = LLMConfig(**{**asdict(cfg.llm), **raw_data["llm"]})
            if "watcher" in raw_data and isinstance(raw_data["watcher"], dict):
                cfg.watcher = WatcherConfig(**{**asdict(cfg.watcher), **raw_data["watcher"]})
            if "scheduler" in raw_data and isinstance(raw_data["scheduler"], dict):
                cfg.scheduler = SchedulerConfig(**{**asdict(cfg.scheduler), **raw_data["scheduler"]})
            if "collector" in raw_data and isinstance(raw_data["collector"], dict):
                cfg.collector = CollectorConfig(**{**asdict(cfg.collector), **raw_data["collector"]})
            if "pipeline" in raw_data and isinstance(raw_data["pipeline"], dict):
                cfg.pipeline = PipelineConfig(**{**asdict(cfg.pipeline), **raw_data["pipeline"]})

            for key in ("root_dir", "log_level", "log_file", "rule_file", "state_file"):
                if key in raw_data:
                    setattr(cfg, key, raw_data[key])

        except Exception as e:
            print(f"[WARN] Failed to load config from {config_path}: {e}")
            print("[INFO] Using default configuration.")

    # Override with environment variables
    if os.environ.get("CW_LLM_API_KEY"):
        cfg.llm.api_key = os.environ["CW_LLM_API_KEY"]
    if os.environ.get("CW_LLM_PROVIDER"):
        cfg.llm.provider = os.environ["CW_LLM_PROVIDER"]
    if os.environ.get("CW_LLM_BASE_URL"):
        cfg.llm.base_url = os.environ["CW_LLM_BASE_URL"]

    # Resolve paths
    cfg.root_dir = Path(cfg.root_dir)
    cfg.raw_dir = cfg.root_dir / "raw" if not Path(cfg.raw_dir).is_absolute() else Path(cfg.raw_dir)
    cfg.wiki_dir = cfg.root_dir / "wiki" if not Path(cfg.wiki_dir).is_absolute() else Path(cfg.wiki_dir)
    cfg.outputs_dir = cfg.root_dir / "outputs" if not Path(cfg.outputs_dir).is_absolute() else Path(cfg.outputs_dir)
    cfg.schema_dir = cfg.root_dir / "schema" if not Path(cfg.schema_dir).is_absolute() else Path(cfg.schema_dir)

    return cfg


def save_config(cfg: CompoundWikiConfig, config_path: Optional[Path | str] = None) -> None:
    """Save current configuration to JSON file."""
    if config_path is None:
        config_path = DEFAULT_CONFIG_FILE
    config_path = Path(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "root_dir": str(cfg.root_dir),
        "log_level": cfg.log_level,
        "log_file": cfg.log_file,
        "rule_file": cfg.rule_file,
        "state_file": cfg.state_file,
        "llm": asdict(cfg.llm),
        "watcher": asdict(cfg.watcher),
        "scheduler": asdict(cfg.scheduler),
        "collector": asdict(cfg.collector),
        "pipeline": asdict(cfg.pipeline),
    }

    # Mask API key before saving
    if data["llm"]["api_key"]:
        data["llm"]["api_key"] = data["llm"]["api_key"][:8] + "...(masked)" if len(data["llm"]["api_key"]) > 8 else "(masked)"

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def generate_default_config(path: Optional[Path | str] = None) -> None:
    """Generate a default config.json template with comments."""
    if path is None:
        path = DEFAULT_CONFIG_FILE
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    default_cfg = CompoundWikiConfig()
    save_config(default_cfg, path)
    print(f"[OK] Default config generated at: {path}")
    print(f"[TIP] Edit it to add your API key and customize settings.")
