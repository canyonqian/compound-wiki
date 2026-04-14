"""
Enhanced File Watch Source Plugin
==================================

Monitors the raw/ directory (and optionally other directories)
for new files and automatically queues them for ingestion.

This is an upgraded version of auto/watcher.py that integrates
with the plugin system. Supports:
  • Multiple watch directories
  • File type filtering
  • Debouncing + batch collection
  • Cross-platform (inotify on Linux, FSEvents on macOS, ReadDirectoryChangesW on Windows)

Configuration:
    settings:
      watch_dirs: ["raw"]              # Directories to watch (relative to project root)
      file_extensions: [".md", ".txt", ".pdf", ".html", ".json"]
      debounce_seconds: 3             # Wait this long after last change before triggering
      batch_window_seconds: 30        # Collect changes within this window as batch
      recursive: true                 # Watch subdirectories
      ignore_patterns: [".*", "_*"]   # Glob patterns to ignore
"""

import asyncio
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set

from .base import BaseSource, IngestItem, SourceConfig, SourceType, ContentType

logger = logging.getLogger("cw-source-filewatch")


class EnhancedFileWatchSource(BaseSource):
    """
    Enhanced file system watcher.
    
    Uses watchdog library if available, with polling fallback.
    """

    @property
    def source_type(self) -> SourceType:
        return SourceType.FILE_WATCH

    @property
    def display_name(self) -> str:
        return "File Watcher"

    @property
    def description(self) -> str:
        return "Monitor directories for new files (always active)"

    async def start(self):
        await super().start()
        
        project = Path(self.config.settings.get("project_dir", ".")).resolve()
        dir_names = self.config.settings.get("watch_dirs", ["raw"])
        
        self._watch_paths: List[Path] = []
        for d in dir_names:
            p = project / d
            p.mkdir(parents=True, exist_ok=True)
            self._watch_paths.append(p)
        
        self._extensions = set(
            self.config.settings.get("file_extensions", 
                                     [".md", ".txt", ".pdf", ".html", ".json", ".org", ".rst"])
        )
        self._debounce = float(self.config.settings.get("debounce_seconds", 3))
        self._batch_window = float(self.config.settings.get("batch_window_seconds", 30))
        self._ignore = set(self.config.settings.get("ignore_patterns", [".*", "_*", "~*"]))
        
        self._queue: List[IngestItem] = []
        self._pending: Dict[Path, float] = {}  # path → event time
        self._known_files: Set[str] = set()     # SHA256 hashes of known files
        
        # Scan existing files so we only detect NEW ones
        for wp in self._watch_paths:
            for f in wp.rglob("*"):
                if f.is_file():
                    self._known_files.add(self._file_hash(f))
        
        logger.info(f"📁 File watcher started — watching {len(self._watch_paths)} dirs")
        
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
            
            class Handler(FileSystemEventHandler):
                def __init__(self, parent):
                    self.parent = parent
                
                def on_created(self, event):
                    p = Path(event.src_path)
                    if not event.is_directory and self.parent._should_process(p):
                        self.parent._pending[p] = asyncio.get_event_loop().time()
                
                def on_modified(self, event):
                    p = Path(event.src_path)
                    if not event.is_directory and self.parent._should_process(p):
                        self.parent._pending[p] = asyncio.get_event_loop().time()
            
            self._observer = Observer()
            handler = Handler(self)
            for wp in self._watch_paths:
                self._observer.schedule(handler, str(wp), recursive=True)
            self._observer.start()
            logger.info("📁 Using watchdog (native FS events)")
            
        except ImportError:
            logger.info("📁 Using polling fallback (install watchdog for native events)")
            self._task = asyncio.create_task(self._poll_loop())

        # Start debouncer task
        self._process_task = asyncio.create_task(self._debounce_loop())

    async def stop(self):
        if hasattr(self, '_observer'):
            self._observer.stop()
        if hasattr(self, '_task'):
            self._task.cancel()
        if hasattr(self, '_process_task'):
            self._process_task.cancel()
        await super().stop()

    async def collect(self) -> List[IngestItem]:
        items = list(self._queue)
        self._queue.clear()
        return items

    def _should_process(self, path: Path) -> bool:
        """Check if a file should be processed."""
        name = path.name
        
        # Check extension
        if self._extensions and path.suffix.lower() not in self._extensions:
            return False
        
        # Check ignore patterns
        for pattern in self._ignore:
            import fnmatch
            if fnmatch.fnmatch(name, pattern):
                return False
        
        # Skip hidden files
        if name.startswith("."):
            return False
        
        return True

    async def _poll_loop(self):
        """Fallback polling loop when watchdog unavailable."""
        while self._running:
            try:
                for wp in self._watch_paths:
                    if not wp.exists():
                        continue
                    now = asyncio.get_event_loop().time()
                    
                    for f in wp.rglob("*"):
                        if f.is_file() and self._should_process(f):
                            fhash = self._file_hash(f)
                            if fhash not in self._known_files:
                                self._pending[f] = now
                                self._known_files.add(fhash)
                            else:
                                # Modified?
                                mtime = f.stat().st_mtime
                                if f not in self._pending or mtime > self._pending.get(f, 0):
                                    self._pending[f] = now
                                    
            except Exception as e:
                logger.debug(f"Poll error: {e}")
            
            await asyncio.sleep(2)

    async def _debounce_loop(self):
        """Process pending files after debounce + batch window."""
        while self._running:
            await asyncio.sleep(min(self._debounce, 1))
            
            now = asyncio.get_event_loop().time()
            ready = [
                p for p, t in self._pending.items()
                if (now - t) >= self._debounce
            ]
            
            if ready:
                for p in ready:
                    del self._pending[p]
                    
                    try:
                        content = p.read_text(encoding="utf-8", errors="replace")
                        if len(content.strip()) < 10:
                            continue
                        
                        item = IngestItem(
                            content=content,
                            title=p.stem,
                            source_type=SourceType.FILE_WATCH,
                            content_type=self._detect_type(p),
                            metadata={
                                "file_path": str(p),
                                "extension": p.suffix,
                                "size": len(content),
                            },
                        )
                        
                        if self.validate_item(item):
                            self._queue.append(item)
                            logger.info(f"📁 New file: {p.name}")
                            
                    except Exception as e:
                        logger.warning(f"Error reading {p}: {e}")

    @staticmethod
    def _file_hash(path: Path) -> str:
        """Get SHA256 hash of file."""
        h = hashlib.sha256()
        h.update(str(path).encode())
        h.update(path.stat().st_size.to_bytes(8, 'little'))
        return h.hexdigest()

    @staticmethod
    def _detect_type(path: Path) -> ContentType:
        ext_map = {
            ".pdf": ContentType.PDF,
            ".py": ContentType.CODE, ".js": ContentType.CODE,
            ".ts": ContentType.CODE, ".java": ContentType.CODE,
            ".go": ContentType.CODE, ".rs": ContentType.CODE,
            ".md": ContentType.ARTICLE, ".txt": ContentType.NOTE,
            ".html": ContentType.ARTICLE, ".htm": ContentType.ARTICLE,
            ".org": ContentType.NOTE, ".rst": ContentType.ARTICLE,
            ".json": ContentType.ARTICLE,
        }
        return ext_map.get(path.suffix.lower(), ContentType.UNKNOWN)
