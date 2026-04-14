"""
Compound Wiki - File Watcher
==============================
Monitors raw/ directory for new/changed files and auto-triggers ingestion.
Uses watchdog library with debouncing and batch processing.
"""

from __future__ import annotations

import fnmatch
import logging
import threading
import time
from pathlib import Path

# Optional dependency: pip install watchdog
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    print("[WARN] watchdog not installed. Run: pip install watchdog")
    print("[INFO] Falling back to polling mode.")

logger = logging.getLogger("compound_wiki.watcher")


class RawFileHandler(FileSystemEventHandler):
    """Handles file system events in raw/ directory."""

    def __init__(self, watcher_instance: "FileWatcher"):
        super().__init__()
        self.w = watcher_instance

    def on_created(self, event: FileCreatedEvent) -> None:
        if not event.is_directory:
            self.w._on_file_event(event.src_path, "created")

    def on_modified(self, event: FileModifiedEvent) -> None:
        if not event.is_directory:
            self.w._on_file_event(event.src_path, "modified")


class FileWatcher:
    """
    Monitors raw/ for new files.
    
    Modes:
      - watchdog (default): Real-time OS-level events. Requires `pip install watchdog`
      - polling: Fallback — checks directory every N seconds
    """

    def __init__(self, raw_dir: Path, on_new_files_callback, config=None):
        self.raw_dir = Path(raw_dir)
        self.on_new_files = on_new_files_callback
        self.config = config or {}

        # Watch settings
        self.debounce_seconds = self.config.get("debounce_seconds", 3.0)
        self.batch_mode = self.config.get("batch_mode", True)
        self.batch_wait_seconds = self.config.get("batch_wait_seconds", 30.0)
        self.file_patterns = self.config.get("file_patterns", ["*"])
        self.ignore_patterns = self.config.get("ignore_patterns", [".DS_Store", ".gitkeep"])
        self.enabled = self.config.get("enabled", True)

        # State
        self._pending_files: list[str] = []
        self._last_event_time: float = 0.0
        self._timer: threading.Timer | None = None
        self._observer: Observer | None = None
        self._polling_thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.Lock()

    def _should_process(self, filename: str) -> bool:
        """Check if a file matches include/exclude patterns."""
        # Check ignore patterns first
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return False

        # Check include patterns
        for pattern in self.file_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True

        return False  # Default: only process if explicitly matched

    def _on_file_event(self, file_path: str, event_type: str) -> None:
        """Called when a file event is detected."""
        path = Path(file_path)

        # Only watch within raw_dir
        try:
            path.relative_to(self.raw_dir)
        except ValueError:
            return

        if not path.is_file():
            return

        if not self._should_process(path.name):
            return

        with self._lock:
            self._pending_files.append(str(path))
            self._last_event_time = time.time()

            if self.batch_mode:
                self._schedule_batch()
            else:
                self._schedule_immediate()

        logger.info(f"📥 {event_type.upper()}: {path.name} (pending: {len(self._pending_files)})")

    def _schedule_immediate(self) -> None:
        """Schedule processing after debounce period (single-file)."""
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(
            self.debounce_seconds,
            self._flush_pending,
        )
        self._timer.daemon = True
        self._timer.start()

    def _schedule_batch(self) -> None:
        """Schedule batch processing after quiet window."""
        if self._timer is not None:
            self._timer.cancel()

        wait_time = max(self.batch_wait_seconds, self.debounce_seconds)
        self._timer = threading.Timer(wait_time, self._flush_pending)
        self._timer.daemon = True
        self._timer.start()

    def _flush_pending(self) -> None:
        """Flush all pending files to the callback."""
        with self._lock:
            files_to_process = list(set(self._pending_files))
            self._pending_files.clear()

        if files_to_process:
            logger.info(f"🚀 Flushing {len(files_to_process)} file(s) to pipeline...")
            try:
                self.on_new_files(files_to_process)
            except Exception as e:
                logger.error(f"Error in ingest callback: {e}", exc_info=True)

    def start(self) -> None:
        """Start watching."""
        if not self.enabled:
            logger.info("Watcher disabled by configuration.")
            return

        self._running = True

        if HAS_WATCHDOG:
            self._start_watchdog()
        else:
            self._start_polling()

        logger.info(f"👀 Watching: {self.raw_dir}")
        logger.info(f"   Mode: {'watchdog' if HAS_WATCHDOG else 'polling'}")
        logger.info(f"   Batch: {'ON ({self.batch_wait_seconds}s)' if self.batch_mode else 'OFF'}")

    def _start_watchdog(self) -> None:
        """Start using watchdog (real-time events)."""
        self._observer = Observer()
        handler = RawFileHandler(self)
        self._observer.schedule(handler, str(self.raw_dir), recursive=True)
        self._observer.daemon = True
        self._observer.start()

    def _start_polling(self) -> None:
        """Fallback polling mode."""
        poll_interval = 5.0  # Check every 5 seconds
        known_files = set()

        def poll_loop():
            while self._running:
                try:
                    current_files = set(str(p) for p in self.raw_dir.rglob("*") if p.is_file())
                    new_files = current_files - known_files

                    for f in sorted(new_files):
                        path = Path(f)
                        if self._should_process(path.name):
                            self._on_file_event(f, "created")

                    known_files = current_files

                except Exception as e:
                    logger.error(f"Polling error: {e}")

                time.sleep(poll_interval)

        self._polling_thread = threading.Thread(target=poll_loop, daemon=True, name="CW-Poller")
        self._polling_thread.start()

    def stop(self) -> None:
        """Stop watching."""
        self._running = False
        logger.info("⏹ Stopping watcher...")

        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

        if self._polling_thread is not None:
            self._polling_thread.join(timeout=5)
            self._polling_thread = None

        # Flush any remaining pending files
        if self._pending_files:
            logger.info(f"Flushing {len(self._pending_files)} remaining file(s)...")
            self._flush_pending()

        logger.info("Watcher stopped.")

    @property
    def is_running(self) -> bool:
        return self._running
