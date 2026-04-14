"""
Compound Wiki - Main Agent Entry Point
=======================================
Unified entry point that orchestrates all modules:
  - File Watcher (auto-detects new files in raw/)
  - Ingestion Pipeline (processes raw → wiki via LLM)
  - Web Collector (fetches URLs → raw/)
  - Scheduler (cron-like automation)
  - State Manager (tracks everything)

Usage:
  python auto/agent.py start     # Start full agent with all modules
  python auto/agent.py ingest    # One-shot ingestion
  python auto/agent.py query "question"
  python auto/agent.py lint      # Health check
  python auto/agent.py collect https://example.com/article
  python auto/agent.py status    # Show wiki stats
  python auto/agent.py init      # First-time setup
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import all modules
from auto.config import load_config, generate_default_config, CompoundWikiConfig
from auto.state import StateManager, WikiState
from auto.watcher import FileWatcher
from auto.pipeline import IngestionPipeline, LLMClient
from auto.collector import WebCollector
from auto.scheduler import TaskScheduler


# ── Logging Setup ──────────────────────────────────────────

def setup_logging(level: str = "INFO", log_file: str | None = None):
    fmt = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    datefmt = "%H:%M:%S"

    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        datefmt=datefmt,
        handlers=handlers,
        force=True,
    )


# ── Banner ──────────────────────────────────────────────────

BANNER = r"""
╔═══════════════════════════════════════════════════╗
║                                                   ║
║   🧠 Compound Wiki — AI-Driven Memory System      ║
║   Make knowledge compound over time               ║
║                                                   ║
║   Auto Mode: ON                                   ║
║   Modules: Watcher · Pipeline · Collector · Scheduler ║
║                                                   ║
╚═══════════════════════════════════════════════════╝
"""


class CompoundWikiAgent:
    """
    The main agent that orchestrates all Compound Wiki modules.
    
    Lifecycle:
      1. Load config & state
      2. Initialize all modules (LLM client, pipeline, watcher, collector, scheduler)
      3. Connect modules together (callbacks)
      4. Start background services
      5. Wait for commands / run interactively
    
    Architecture:
    
    ┌──────────┐     ┌────────────┐     ┌────────┐
    │ Web URLs │────▶│  Collector  │────▶│  raw/  │
    └──────────┘     └────────────┘     └───┬────┘
                                          │ file events
                    ┌───────────────────────▼───────────────┐
                    │            FileWatcher                 │
                    └───────────────────────┬───────────────┘
                                          │ on_new_files()
                    ┌───────────────────────▼───────────────┐
                    │         IngestionPipeline              │
                    │  (raw files + CLAUDE.md) ──▶ LLM      │
                    └───────────────────────┬───────────────┘
                                          │ write pages
                              ┌───────────▼───────────┐
                              │       wiki/            │
                              │ concept/entity/synth   │
                              └───────────┬───────────┘
                                         │
              ┌──────────────────────────┼──────────────────┐
              ▼                          ▼                  ▼
       ┌──────────────┐          ┌────────────┐    ┌────────────┐
       │   Query()    │          │   LINT()   │    │ Scheduler  │
       │ Q → A + archive│       │ Health check│    │ Cron tasks │
       └──────────────┘          └────────────┘    └────────────┘
    """

    def __init__(self, config_path: str | Path | None = None):
        # Load configuration
        self.cfg: CompoundWikiConfig = load_config(config_path)

        # Setup logging
        setup_logging(self.cfg.log_level, self.cfg.log_file)
        
        self.logger = logging.getLogger("compound_wiki")

        # Initialize state manager
        self.state = StateManager(str(self.cfg.root_dir / getattr(self.cfg, 'state_file', 'auto/state/state.json')))

        # Initialize LLM client
        self.llm = LLMClient(self.cfg.llm.__dict__)

        # Initialize pipeline (depends on LLM + state)
        self.pipeline = IngestionPipeline(self.cfg, self.state, self.llm)

        # Initialize collector
        self.collector = WebCollector(self.cfg.collector.__dict__)

        # Initialize scheduler (depends on pipeline)
        self.scheduler = TaskScheduler(pipeline=self.pipeline, config=self.cfg)

        # Initialize watcher (starts after pipeline ready)
        self.watcher = None

        # Running flag
        self._running = False

    def _init_watcher(self) -> FileWatcher:
        """Initialize and configure the file watcher."""
        watcher_config = self.cfg.watcher.__dict__
        watcher = FileWatcher(
            raw_dir=self.cfg.raw_dir,
            on_new_files_callback=self._on_raw_files_detected,
            config=watcher_config,
        )
        return watcher

    def _on_raw_files_detected(self, file_paths: list[str]) -> None:
        """Callback: watcher detected new files, trigger ingestion."""
        self.logger.info(f"📥 Watcher detected {len(file_paths)} new/changed file(s)")
        try:
            results = self.pipeline.run(files=file_paths)

            # Optionally run LINT after N ingestions
            total_ingests = len(self.state.state.ingests)
            lint_every = getattr(self.cfg.pipeline, 'lint_every_n_ingests', 10)
            if total_ingests > 0 and total_ingests % lint_every == 0:
                self.logger.info(f"🔍 Running scheduled LINT (every {lint_every} ingestions)...")
                self.pipeline.lint(auto_fix=False)

        except Exception as e:
            self.logger.error(f"Auto-ingest failed: {e}", exc_info=True)

    def start(self) -> None:
        """Start the full agent with all modules."""
        print(BANNER)
        print(f"  Root: {self.cfg.root_dir}")
        print(f"  Raw:  {self.cfg.raw_dir}")
        print(f"  Wiki: {self.cfg.wiki_dir}")
        print()

        self._running = True

        # Start file watcher
        self.watcher = self._init_watcher()
        self.watcher.start()

        # Register scheduler callbacks
        self.scheduler.register_callback("ingest", lambda: self.pipeline.run())
        self.scheduler.register_callback("lint", lambda: self.pipeline.lint(auto_fix=False))

        # Start scheduler
        self.scheduler.start()

        # Print stats
        stats = self.state.get_stats()
        print(f"  📊 Wiki Stats:")
        print(f"     Tracked files: {stats['tracked_files']}")
        print(f"     Pages created: {stats['total_pages_created']}")
        print(f"     Ingestions:    {stats['total_ingests']}")
        print()

        print("✅ Agent is running. Press Ctrl+C to stop.")
        print()

        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n⏹ Shutting down...")
            self.stop()

    def stop(self) -> None:
        """Gracefully shut down all modules."""
        self._running = False

        if self.watcher is not None:
            self.watcher.stop()
        self.scheduler.stop()

        self.state.save()
        print("✅ Agent stopped. All state saved.")

    # ── CLI Command Handlers ──────────────────────────────

    def cmd_init(self) -> None:
        """First-time setup: generate default config and directory structure."""
        print("\n🔧 Initializing Compound Wiki...")

        # Create directories
        for d in ["raw", "wiki/concept", "wiki/entity", "wiki/synthesis", 
                   "outputs", "schema/templates", "auto/state", "auto/logs", 
                   "examples/raw-sample", "raw/collected"]:
            (self.cfg.root_dir / d).mkdir(parents=True, exist_ok=True)
            print(f"  📁 Created: {d}/")

        # Generate default config
        from auto.config import DEFAULT_CONFIG_FILE
        generate_default_config(DEFAULT_CONFIG_FILE)

        # Generate .gitkeep files
        for d in ["raw", "outputs"]:
            keep_file = self.cfg.root_dir / d / ".gitkeep"
            if not keep_file.exists():
                keep_file.write_text("# Keep this directory in git\n")
                print(f"  📄 Created: {d}/.gitkeep")

        print(f"\n✅ Initialization complete!")
        print(f"\nNext steps:")
        print(f"  1. Edit auto/config.json to add your API key:")
        print(f"     Set llm.api_key to your Anthropic/OpenAI key")
        print(f"  2. Drop your first document into raw/")
        print(f"  3. Run: python auto/agent.py ingest")
        print(f"     Or: python auto/agent.py start   (full auto mode)")

    def cmd_ingest(self) -> None:
        """One-shot ingestion of pending files."""
        print("\n🚀 Running one-shot ingestion...")
        results = self.pipeline.run()
        print(f"\n{'='*50}")
        print(f"Files processed: {results.get('files_processed', 0)}")
        print(f"Pages created:   {len(results.get('pages_created', []))}")
        print(f"Pages updated:   {len(results.get('pages_updated', []))}")
        errors = results.get('errors', [])
        if errors:
            print(f"\n❌ Errors ({len(errors)}):")
            for e in errors:
                print(f"  - {e}")

    def cmd_query(self, question: str) -> None:
        """Query the wiki."""
        answer = self.pipeline.query(question, archive=True)
        print(f"\n{answer}")

    def cmd_lint(self) -> None:
        """Run health check."""
        result = self.pipeline.lint(auto_fix=False)
        print(result["report"])

    def cmd_collect(self, urls: str | list[str]) -> None:
        """Collect web content into raw/."""
        if isinstance(urls, str):
            urls = urls.split(",")
        results = self.collector.collect(urls)

        print(f"\n🌐 Collection Results:")
        ok = sum(1 for r in results if r["status"] == "ok")
        fail = sum(1 for r in results if r["status"] != "ok")
        print(f"  ✅ Success: {ok}  |  ❌ Failed: {fail}")

    def cmd_status(self) -> None:
        """Show wiki statistics."""
        stats = self.state.get_stats()

        print("\n" + "=" * 50)
        print("  🧠 Compound Wiki — Status Report")
        print("=" * 50)
        print(f"\n  📂 Files:")
        print(f"     Tracked:    {stats['tracked_files']}")
        print(f"     Processed:  {stats['processed_files']}")
        print(f"     Pending:    {stats['pending_files']}")
        print(f"     Errors:     {stats['error_files']}")

        print(f"\n  📝 Knowledge Base:")
        print(f"     Pages created: {stats['total_pages_created']}")
        print(f"     Pages updated: {stats['total_pages_updated']}")

        print(f"\n  ⚙️ Operations:")
        print(f"     Ingestions:  {stats['total_ingests']}")
        print(f"     LINT checks: {stats['total_lints']}")
        print(f"     Issues fixed: {stats['issues_fixed']}")
        print(f"     Queries:     {stats['total_queries']}")

        print(f"\n  ⏱ Timeline:")
        print(f"     Started:     {stats['started_at'][:19]}")
        print(f"     Last ingest: {stats['last_ingest'][:19] if stats['last_ingest'] else 'never'}")
        print(f"     Last LINT:   {stats['last_lint'][:19] if stats['last_lint'] else 'never'}")


# ── CLI Interface ─────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="compound-wiki",
        description="🧠 Compound Wiki — AI-driven compound memory system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s init                  First-time setup
  %(prog)s start                 Run full auto mode (watcher + scheduler)
  %(prog)s ingest                Process pending raw files once
  %(prog)s query "What is X?"    Query the wiki
  %(prog)s lint                  Run health check
  %(prog)s collect <URL>         Fetch a webpage into raw/
  %(prog)s status                Show statistics
        """,
    )

    parser.add_argument("command", nargs="?", default=None,
                        help="Command to execute (start/ingest/query/lint/collect/status/init)")
    parser.add_argument("args", nargs="*", help="Arguments for command")
    parser.add_argument("--config", "-c", help="Path to config.json")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")

    args = parser.parse_args()

    # Handle no-command case (default to --help or status)
    if args.command is None:
        if os.path.exists(str(Path(__file__).resolve().parent.parent / "auto" / "state" / "state.json")):
            args.command = "status"
        else:
            parser.print_help()
            return

    # Adjust log level
    log_level = "DEBUG" if args.verbose else "INFO"

    # Initialize agent
    try:
        agent = CompoundWikiAgent(config_path=args.config)
    except Exception as e:
        print(f"❌ Initialization error: {e}")
        sys.exit(1)

    # Dispatch command
    command = args.command.lower()

    if command == "start":
        agent.start()

    elif command == "init":
        agent.cmd_init()

    elif command == "ingest":
        agent.cmd_ingest()

    elif command == "query":
        question = " ".join(args.args) if args.args else input("Enter your question: ")
        agent.cmd_query(question)

    elif command == "lint":
        agent.cmd_lint()

    elif command == "collect":
        url_input = " ".join(args.args) if args.args else input("Enter URL(s) (comma-separated): ")
        agent.cmd_collect(url_input)

    elif command == "status":
        agent.cmd_status()

    else:
        print(f"❌ Unknown command: {command}")
        print(f"Run without arguments for help.")
        sys.exit(1)


if __name__ == "__main__":
    main()
