"""
Data Source Plugins
====================

Each source is a self-contained plugin that collects content from a specific channel.
All sources implement BaseSource and produce IngestItem objects.

Available Sources:
  • API Source      — REST endpoint, receive POST requests
  • Clipboard       — Monitor system clipboard for text
  • Email           — Watch IMAP inbox for new mail
  • RSS             — Poll RSS/Atom feeds
  • Bot (Telegram)  — Receive forwarded messages
  • Bot (Discord)   — Monitor channels
  • Browser         — Web clipper / bookmarklet
  • Webhook         — Zapier/IFTTT/n8n integration
  • File Watch      — Enhanced file watcher (replaces auto/watcher.py)
"""

from .base import (
    BaseSource, SourceType, IngestItem,
    ContentType, SourceConfig,
)
from .api_source import APISource
from .clipboard import ClipboardSource
from .email_source import EmailSource
from .rss_source import RSSSource
from .bot_telegram import TelegramBotSource
from .bot_discord import DiscordBotSource
from .browser import BrowserClipperSource
from .webhook_source import WebhookSource
from .file_watch import EnhancedFileWatchSource

# Registry of all built-in sources
SOURCE_REGISTRY = {
    "api": APISource,
    "clipboard": ClipboardSource,
    "email": EmailSource,
    "rss": RSSSource,
    "bot_telegram": TelegramBotSource,
    "bot_discord": DiscordBotSource,
    "browser": BrowserClipperSource,
    "webhook": WebhookSource,
    "file_watch": EnhancedFileWatchSource,
}


class SourceRegistry:
    """
    Central registry for all data sources.
    
    Usage:
        registry = SourceRegistry()
        registry.enable("clipboard")
        registry.enable("rss", settings={"feeds": [...]})
        
        # Start all enabled sources
        await registry.start_all()
        
        # Collect from all sources
        items = await registry.collect_all()
    """

    def __init__(self):
        self._sources: Dict[str, BaseSource] = {}
        self._configs: Dict[str, SourceConfig] = {}

    def register(self, name: str, source: BaseSource):
        """Register a custom source."""
        self._sources[name] = source

    def enable(self, name: str, config: Optional[SourceConfig] = None):
        """Enable a built-in source by name."""
        if name not in SOURCE_REGISTRY:
            raise ValueError(f"Unknown source: {name}. Available: {list(SOURCE_REGISTRY.keys())}")
        
        source_class = SOURCE_REGISTRY[name]
        self._sources[name] = source_class(config or SourceConfig(name=name))
        self._configs[name] = config

    def disable(self, name: str):
        """Disable a running source."""
        if name in self._sources:
            import asyncio
            asyncio.get_event_loop().run_until_complete(self._sources[name].stop())
            del self._sources[name]

    def get(self, name: str) -> Optional[BaseSource]:
        """Get a source by name."""
        return self._sources.get(name)

    def list_sources(self) -> List[Dict[str, Any]]:
        """List all available and enabled sources."""
        result = []
        for name, cls in SOURCE_REGISTRY.items():
            enabled = name in self._sources
            instance = self._sources.get(name)
            result.append({
                "name": name,
                "display_name": cls.display_name if hasattr(cls, 'display_name') else name,
                "type": cls.source_type.value if hasattr(cls, 'source_type') else "custom",
                "enabled": enabled,
                "running": instance.running if instance else False,
            })
        return result

    async def start_all(self):
        """Start all enabled sources."""
        for name, source in self._sources.items():
            try:
                await source.start()
            except Exception:
                pass  # Log but don't crash other sources

    async def stop_all(self):
        """Stop all running sources."""
        for name, source in self._sources.items():
            try:
                await source.stop()
            except Exception:
                pass

    async def collect_all(self) -> List[IngestItem]:
        """Collect new items from all enabled sources."""
        all_items = []
        for name, source in self._sources.items():
            if not source.running:
                continue
            try:
                items = await source.collect()
                for item in items:
                    if source.validate_item(item):
                        item.metadata["_source"] = name
                        all_items.append(item)
            except Exception as e:
                print(f"[{name}] Collect error: {e}")
        return all_items


def get_all_sources() -> List[str]:
    """Get list of all available source names."""
    return list(SOURCE_REGISTRY.keys())
