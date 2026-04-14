"""
RSS Source Plugin
=================

Subscribe to RSS/Atom feeds for automatic content ingestion.

Perfect for:
  • Tech blogs (Hacker News RSS, individual dev blogs)
  • News sites (BBC, Reuters, NYT)
  • Academic feeds (arXiv new submissions)
  • Podcast show notes
  • YouTube channel RSS (for video transcripts)

Configuration:
    settings:
      feeds:
        - url: "https://hnrss.org/newest?points=100"
          tags: ["tech", "hacker-news"]
        - url: "https://arxiv.org/rss/cs.AI"
          tags: ["ai", "research", "paper"]
      max_items_per_feed: 10
      full_content: true       # try to fetch full article text
      only_new: true           # only ingest items since last check
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List

from .base import BaseSource, IngestItem, SourceConfig, SourceType, ContentType

logger = logging.getLogger("cw-source-rss")


class RSSSource(BaseSource):
    """RSS / Atom feed subscriber."""

    @property
    def source_type(self) -> SourceType:
        return SourceType.RSS

    @property
    def display_name(self) -> str:
        return "RSS Feed Reader"

    @property
    def description(self) -> str:
        return "Subscribe to RSS/Atom feeds for auto-ingestion"

    async def start(self):
        await super().start()
        
        self._queue: List[IngestItem] = []
        self._known_urls: set = set()
        self._feeds = self.config.settings.get("feeds", [])
        self._poll_interval = int(self.config.settings.get("poll_interval", 300))  # 5 min default
        self._max_per_feed = int(self.config.settings.get("max_items_per_feed", 10))
        
        logger.info(f"📡 RSS reader started ({len(self._feeds)} feeds, interval={self._poll_interval}s)")
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self):
        if hasattr(self, '_task'):
            self._task.cancel()
        await super().stop()

    async def collect(self) -> List[IngestItem]:
        items = list(self._queue)
        self._queue.clear()
        return items

    async def _poll_loop(self):
        while self._running:
            try:
                await self._fetch_all_feeds()
            except Exception as e:
                logger.warning(f"RSS poll error: {e}")
            await asyncio.sleep(self._poll_interval)

    async def _fetch_all_feeds(self):
        """Fetch all configured feeds."""
        import feedparser
        
        for feed_config in self._feeds:
            try:
                url = feed_config["url"]
                feed_tags = feed_config.get("tags", [])
                
                logger.debug(f"Fetching feed: {url}")
                parsed = feedparser.parse(url)
                
                count = 0
                for entry in reversed(parsed.entries[:self._max_per_feed * 2]):  # More to account for known
                    link = entry.get("link", "")
                    
                    # Skip already-known URLs
                    if link in self._known_urls:
                        continue
                    
                    count += 1
                    if count > self._max_per_feed:
                        break
                    
                    self._known_urls.add(link)
                    
                    # Extract content
                    content = (
                        entry.get("content", [{}])[0].get("value", "")
                        or entry.get("summary", "")
                        or entry.get("description", "")
                    )
                    title = entry.get("title", "(Untitled)")
                    
                    item = IngestItem(
                        content=content,
                        title=title,
                        url=link,
                        source_type=SourceType.RSS,
                        content_type=ContentType.ARTICLE,
                        metadata={
                            "feed_url": url,
                            "feed_title": parsed.feed.get("title", ""),
                            "published": entry.get("published", ""),
                            "author": entry.get("author", ""),
                            **entry,
                        },
                        tags=feed_tags,
                    )
                    
                    if self.validate_item(item):
                        self._queue.append(item)
                        logger.info(f"📡 RSS: {title[:50]}")
                
            except Exception as e:
                logger.warning(f"Feed {feed_config.get('url', '?')} error: {e}")
