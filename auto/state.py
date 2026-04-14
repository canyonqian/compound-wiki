"""
Compound Wiki - State Manager
==============================
Tracks ingestion history, processed files, and operational state.
Enables incremental updates and prevents duplicate processing.
"""

from __future__ import annotations

import json
import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict


@dataclass
class FileInfo:
    """Metadata about a tracked file."""
    path: str
    size: int
    mtime: float           # modification timestamp
    sha256: str            # content hash
    first_seen: str        # ISO format datetime
    last_processed: Optional[str] = None
    process_count: int = 0
    status: str = "pending"  # pending, processing, done, error, superseded


@dataclass
class IngestRecord:
    """A single ingest operation record."""
    id: str
    timestamp: str         # ISO format
    files: list[str]       # file paths processed
    pages_created: list[str]
    pages_updated: list[str]
    errors: list[str]
    duration_seconds: float
    trigger: str = "manual"  # manual, watcher, scheduler, api


@dataclass
class LintRecord:
    """A single LINT check record."""
    id: str
    timestamp: str
    issues_found: int
    issues_fixed: int
    warnings: list[str]
    errors: list[str]
    duration_seconds: float


@dataclass
class QueryRecord:
    """A single query/answer record."""
    id: str
    timestamp: str
    question: str
    answer_page: Optional[str] = None  # archived page path, if any
    archived: bool = False


@dataclass
class WikiState:
    """Complete runtime state."""
    version: str = "1.0.0"

    files: dict[str, FileInfo] = field(default_factory=dict)   # path -> FileInfo
    ingests: list[IngestRecord] = field(default_factory=list)
    lints: list[LintRecord] = field(default_factory=list)
    queries: list[QueryRecord] = field(default_factory=list)

    # Counters
    total_pages_created: int = 0
    total_pages_updated: int = 0
    total_files_processed: int = 0
    total_lint_issues_fixed: int = 0

    # Stats
    last_ingest: Optional[str] = None
    last_lint: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())


class StateManager:
    """Persists and loads wiki state to/from disk."""

    def __init__(self, state_file: str = "auto/state/state.json"):
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state: WikiState = self._load()

    def _load(self) -> WikiState:
        """Load state from disk."""
        if not self.state_file.exists():
            return WikiState()
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return WikiState(
                version=data.get("version", "1.0.0"),
                files={k: FileInfo(**v) for k, v in data.get("files", {}).items()},
                ingests=[IngestRecord(**r) for r in data.get("ingests", [])],
                lints=[LintRecord(**r) for r in data.get("lints", [])],
                queries=[QueryRecord(**r) for r in data.get("queries", [])],
                total_pages_created=data.get("total_pages_created", 0),
                total_pages_updated=data.get("total_pages_updated", 0),
                total_files_processed=data.get("total_files_processed", 0),
                total_lint_issues_fixed=data.get("total_lint_issues_fixed", 0),
                last_ingest=data.get("last_ingest"),
                last_lint=data.get("last_lint"),
                started_at=data.get("started_at", datetime.now().isoformat()),
            )
        except Exception as e:
            print(f"[WARN] Failed to load state: {e}. Starting fresh.")
            return WikiState()

    def save(self) -> None:
        """Persist state to disk."""
        data = {
            "version": self.state.version,
            "files": {k: asdict(v) for k, v in self.state.files.items()},
            "ingests": [asdict(r) for r in self.state.ingests],
            "lints": [asdict(r) for r in self.state.lints],
            "queries": [asdict(r) for r in self.state.queries],
            "total_pages_created": self.state.total_pages_created,
            "total_pages_updated": self.state.total_pages_updated,
            "total_files_processed": self.state.total_files_processed,
            "total_lint_issues_fixed": self.state.total_lint_issues_fixed,
            "last_ingest": self.state.last_ingest,
            "last_lint": self.state.last_lint,
            "started_at": self.state.started_at,
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def hash_file(file_path: Path) -> str:
        """Compute SHA256 hash of a file."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def register_file(self, file_path: Path) -> FileInfo:
        """Register a file (new or updated). Returns FileInfo."""
        stat = file_path.stat()
        fhash = self.hash_file(file_path)
        rel_path = str(file_path)

        if rel_path in self.state.files:
            existing = self.state.files[rel_path]
            existing.size = stat.st_size
            existing.mtime = stat.st_mtime
            existing.sha256 = fhash
            existing.status = "pending"
            return existing

        info = FileInfo(
            path=rel_path,
            size=stat.st_size,
            mtime=stat.st_mtime,
            sha256=fhash,
            first_seen=datetime.now().isoformat(),
            status="pending",
        )
        self.state.files[rel_path] = info
        return info

    def get_pending_files(self, raw_dir: Path) -> list[FileInfo]:
        """Get files that need processing."""
        pending = []
        if not raw_dir.exists():
            return pending

        for file_path in sorted(raw_dir.rglob("*")):
            if not file_path.is_file():
                continue
            rel_path = str(file_path)

            # Skip known files that haven't changed
            if rel_path in self.state.files:
                existing = self.state.files[rel_path]
                current_mtime = file_path.stat().st_mtime
                if existing.status == "done" and existing.mtime >= current_mtime:
                    continue
                if existing.sha256 == self.hash_file(file_path) and existing.status == "done":
                    continue

            # Register/update the file
            info = self.register_file(file_path)

            # Check size limit (default ~2MB)
            if info.size > 2_000_000:
                print(f"  [SKIP] Too large ({info.size:,} bytes): {file_path.name}")
                continue

            pending.append(info)

        return pending

    def mark_processing(self, file_path: str) -> None:
        if file_path in self.state.files:
            self.state.files[file_path].status = "processing"

    def mark_done(self, file_path: str) -> None:
        if file_path in self.state.files:
            self.state.files[file_path].status = "done"
            self.state.files[file_path].last_processed = datetime.now().isoformat()
            self.state.files[file_path].process_count += 1
            self.state.total_files_processed += 1

    def mark_error(self, file_path: str) -> None:
        if file_path in self.state.files:
            self.state.files[file_path].status = "error"

    def record_ingest(self, record: IngestRecord) -> None:
        self.state.ingests.append(record)
        self.state.last_ingest = record.timestamp
        self.state.total_pages_created += len(record.pages_created)
        self.state.total_pages_updated += len(record.pages_updated)

    def record_lint(self, record: LintRecord) -> None:
        self.state.lints.append(record)
        self.state.last_lint = record.timestamp
        self.state.total_lint_issues_fixed += record.issues_fixed

    def record_query(self, record: QueryRecord) -> None:
        self.state.queries.append(record)

    def get_stats(self) -> dict:
        """Return summary statistics."""
        return {
            "tracked_files": len(self.state.files),
            "processed_files": sum(1 for f in self.state.files.values() if f.status == "done"),
            "pending_files": sum(1 for f in self.state.files.values() if f.status == "pending"),
            "error_files": sum(1 for f in self.state.files.values() if f.status == "error"),
            "total_ingests": len(self.state.ingests),
            "total_pages_created": self.state.total_pages_created,
            "total_pages_updated": self.state.total_pages_updated,
            "total_lints": len(self.state.lints),
            "issues_fixed": self.state.total_lint_issues_fixed,
            "total_queries": len(self.state.queries),
            "queries_archived": sum(1 for q in self.state.queries if q.archived),
            "started_at": self.state.started_at,
            "last_ingest": self.state.last_ingest,
            "last_lint": self.state.last_lint,
        }
