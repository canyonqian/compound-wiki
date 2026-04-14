"""
Base types for source plugins (re-export from parent).
"""

from ...base import (
    BaseSource, BaseAdapter,
    IngestItem, IngestResult,
    SourceConfig, SourceType,
    ContentType,
)

__all__ = [
    "BaseSource", "BaseAdapter",
    "IngestItem", "IngestResult",
    "SourceConfig", "SourceType",
    "ContentType",
]
