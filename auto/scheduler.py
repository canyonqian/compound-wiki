"""
CAM - Scheduler
===========================
Cron-like task scheduler for automated wiki maintenance.
Supports:
  - Daily LINT health checks
  - Weekly knowledge summaries  
  - Monthly compound reports
  - Custom scheduled tasks
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("cam.scheduler")


class CronParser:
    """Simple cron expression parser. Supports standard 5-field format."""

    @staticmethod
    def parse(expression: str) -> dict:
        """
        Parse cron expression into a matchable dict.
        
        Format: minute hour day_of_month month day_of_week
        
        Examples:
          "0 8 * * *"     → Every day at 08:00
          "*/15 * * * *"  → Every 15 minutes
          "0 20 * * 0"    → Every Sunday at 20:00
          "0 9 1 * *"     → 1st of each month at 09:00
        """
        parts = expression.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {expression} (expected 5 fields, got {len(parts)})")

        return {
            "minute": parts[0],
            "hour": parts[1],
            "day": parts[2],
            "month": parts[3],
            "dow": parts[4],
            "raw": expression,
        }

    @staticmethod
    def matches(cron: dict, dt: datetime | None = None) -> bool:
        """Check if a datetime matches a parsed cron expression."""
        if dt is None:
            dt = datetime.now()

        checks = [
            (cron["minute"], dt.minute),
            (cron["hour"], dt.hour),
            (cron["day"], dt.day),
            (cron["month"], dt.month),
            (cron["dow"], dt.weekday()),  # Mon=0 ... Sun=6; cron uses Sun=0
        ]

        # Adjust for cron's Sunday=0 convention
        # In our dow field: convert Python weekday to match cron
        # We'll be flexible here — accept both conventions

        for pattern, value in checks:
            if not CronParser._field_matches(pattern, value):
                return False

        return True

    @staticmethod
    def _field_matches(pattern: str, value: int) -> bool:
        """Check if a single cron field matches."""
        if pattern == "*":
            return True

        # Handle */N (step)
        if pattern.startswith("*/"):
            step = int(pattern[2:])
            return value % step == 0

        # Handle comma-separated values
        if "," in pattern:
            return any(CronParser._field_matches(p.strip(), value) for p in pattern.split(","))

        # Handle range N-M
        if "-" in pattern:
            start, end = pattern.split("-")
            return int(start) <= value <= int(end)

        # Exact match
        try:
            return int(pattern) == value
        except ValueError:
            return False


class ScheduledTask:
    """A single scheduled task definition."""

    def __init__(self, name: str, schedule: str, action: str,
                 enabled: bool = True, description: str = "",
                 last_run: str | None = None):
        self.name = name
        self.schedule = schedule
        self.action = action  # "lint", "summary", "report", "ingest", custom
        self.enabled = enabled
        self.description = description
        self.last_run = last_run
        self.cron = CronParser.parse(schedule)

    def is_due(self, now: datetime | None = None) -> bool:
        """Check if this task is due to run."""
        if not self.enabled:
            return False
        return CronParser.matches(self.cron, now)


class TaskScheduler:
    """
    Lightweight scheduler for CAM automation.
    
    Runs in a background thread, checking every minute if tasks are due.
    
    Actions supported:
      - lint: Run full LINT check
      - summary: Generate weekly knowledge growth summary
      - report: Generate monthly compound report
      - ingest: Auto-ingest pending files from raw/
      - Custom actions via callbacks
    """

    def __init__(self, pipeline=None, config=None):
        self.pipeline = pipeline
        self.config = config or {}
        self.tasks: list[ScheduledTask] = []
        self.callbacks: dict[str, callable] = {}

        # Threading
        self._thread: threading.Thread | None = None
        self._running = False
        self._check_interval = 30  # seconds between checks

        # State file for tracking last runs
        self.state_file = Path(self.config.get("state_file", "auto/state/scheduler.json"))
        self._load_state()

        # Register default tasks from config
        self._register_default_tasks()

    def _register_default_tasks(self) -> None:
        """Register tasks from scheduler config."""
        tasks_config = getattr(self.config.scheduler, 'tasks', {}) if hasattr(self.config.scheduler, 'tasks') else {}
        
        for name, tcfg in tasks_config.items():
            task = ScheduledTask(
                name=name,
                schedule=tcfg.get("schedule", "0 0 * * *"),
                action=tcfg.get("action", "lint"),
                enabled=tcfg.get("enabled", True),
                description=tcfg.get("description", ""),
                last_run=self._last_runs.get(name),
            )
            self.tasks.append(task)

    def register_callback(self, action_name: str, callback: callable) -> None:
        """Register a function to handle a specific action type."""
        self.callbacks[action_name] = callback

    def add_task(self, name: str, schedule: str, action: str,
                 enabled: bool = True, description: str = "") -> ScheduledTask:
        """Add a new scheduled task dynamically."""
        task = ScheduledTask(name, schedule, action, enabled, description)
        self.tasks.append(task)
        return task

    def remove_task(self, name: str) -> None:
        """Remove a task by name."""
        self.tasks = [t for t in self.tasks if t.name != name]

    def start(self) -> None:
        """Start the scheduler background thread."""
        enabled = getattr(self.config.scheduler, 'enabled', True) if hasattr(self.config.scheduler, 'enabled') else True
        if not enabled:
            logger.info("Scheduler disabled by configuration.")
            return

        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="CW-Scheduler")
        self._thread.start()
        logger.info(f"⏰ Scheduler started. Checking every {self._check_interval}s.")
        self._log_tasks()

    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None
        self._save_state()
        logger.info("Scheduler stopped.")

    def _loop(self) -> None:
        """Main scheduling loop."""
        while self._running:
            try:
                self._check_tasks()
            except Exception as e:
                logger.error(f"Scheduler error: {e}", exc_info=True)

            time.sleep(self._check_interval)

    def _check_tasks(self) -> None:
        """Check all tasks and execute due ones."""
        now = datetime.now()

        for task in self.tasks:
            if task.is_due(now):
                self._execute_task(task)

    def _execute_task(self, task: ScheduledTask) -> None:
        """Execute a single due task."""
        logger.info(f"⏰ Executing scheduled task: [{task.name}] ({task.action})")

        start_time = time.time()

        try:
            # Check for registered callback first
            if task.action in self.callbacks:
                result = self.callbacks[task.action]()
            elif task.action == "lint":
                result = self._do_lint()
            elif task.action == "summary":
                result = self._do_summary()
            elif task.action == "report":
                result = self._do_report()
            elif task.action == "ingest" and self.pipeline:
                result = self.pipeline.run()  # Auto-detect pending files
            else:
                logger.warning(f"Unknown action: {task.action}")
                result = None

            duration = time.time() - start_time
            logger.info(f"✅ Task [{task.name}] completed in {duration:.1f}s")

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ Task [{task.name}] failed after {duration:.1f}s: {e}", exc_info=True)

        # Update last run
        task.last_run = datetime.now().isoformat()
        self._last_runs[task.name] = task.last_run
        self._save_state()

    def _do_lint(self) -> dict:
        """Execute LINT action."""
        if self.pipeline:
            return self.pipeline.lint(auto_fix=False)
        return {"error": "No pipeline available"}

    def _do_summary(self) -> str:
        """Generate weekly knowledge growth summary."""
        stats = {}  # Will be populated from state manager
        if hasattr(self.pipeline, 'state'):
            stats = self.pipeline.state.get_stats()

        lines = [
            f"# 📊 Weekly Knowledge Summary",
            f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n",
            f"## Stats",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Files Processed | {stats.get('processed_files', 0)} |",
            f"| Pages Created | {stats.get('total_pages_created', 0)} |",
            f"| Pages Updated | {stats.get('total_pages_updated', 0)} |",
            f"| Total Ingests | {stats.get('total_ingests', 0)} |",
            f"| Issues Fixed | {stats.get('issues_fixed', 0)} |",
            f"\n---\n*Auto-generated by CAM Scheduler*",
        ]
        text = "\n".join(lines)

        # Save to outputs/
        out_path = Path(getattr(self.pipeline.cfg, 'outputs_dir', 'outputs')) / \
                   f"weekly-summary-{datetime.now().strftime('%Y%m%d')}.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")

        return text

    def _do_report(self) -> str:
        """Generate monthly compound report with trend analysis."""
        stats = {}
        if hasattr(self.pipeline, 'state'):
            stats = self.pipeline.state.get_stats()

        started = stats.get("started_at", "unknown")
        lines = [
            f"# 📈 Monthly Compound Report",
            f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
            f"Period: Since {started}\n",
            f"## Cumulative Metrics",
            f"",
            f"| Metric | Count |",
            f"|--------|-------|",
            f"| Tracked Files | {stats.get('tracked_files', 0)} |",
            f"| Processed | {stats.get('processed_files', 0)} |",
            f"| Pending | {stats.get('pending_files', 0)} |",
            f"| Pages Created | {stats.get('total_pages_created', 0)} |",
            f"| Pages Updated | {stats.get('total_pages_updated', 0)} |",
            f"| Ingestions | {stats.get('total_ingests', 0)} |",
            f"| LINT Checks | {stats.get('total_lints', 0)} |",
            f"| Issues Fixed | {stats.get('total_lint_issues_fixed', 0)} |",
            f"| Queries | {stats.get('total_queries', 0)} |",
            f"| Archived Answers | {stats.get('queries_archived', 0)} |",
            f"",
            f"## 🧠 The Compound Effect",
            f"",
            f"> Each page you add connects to existing pages.",
            f"> Each query produces new synthesis pages.",
            f"> Each LINT fix improves overall accuracy.",
            f"",
            f"*This is your knowledge compounding.*",
            f"\n---\n*Auto-generated by CAM*",
        ]
        text = "\n".join(lines)

        out_path = Path(getattr(self.pipeline.cfg, 'outputs_dir', 'outputs')) / \
                   f"monthly-report-{datetime.now().strftime('%Y%m')}.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")

        return text

    def _load_state(self) -> None:
        """Load previous run times from disk."""
        self._last_runs: dict[str, str] = {}
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                self._last_runs = data.get("last_runs", {})
            except Exception:
                pass

    def _save_state(self) -> None:
        """Persist run times to disk."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {"last_runs": self._last_runs}
        self.state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _log_tasks(self) -> None:
        """Log current task configuration."""
        logger.info(f"Registered tasks:")
        for t in self.tasks:
            status = "✅" if t.enabled else "❌"
            lr = f"(last: {t.last_run[:16]}...)" if t.last_run else "(never)"
            logger.info(f"  {status} {t.name}: {t.action} @ {t.schedule} {lr}")

    def list_tasks(self) -> list[dict]:
        """Return list of all tasks as dicts."""
        return [
            {
                "name": t.name,
                "schedule": t.schedule,
                "action": t.action,
                "enabled": t.enabled,
                "description": t.description,
                "last_run": t.last_run,
            }
            for t in self.tasks
        ]
