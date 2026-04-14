"""
Telegram Bot Source Plugin
==========================

Receive forwarded messages from a Telegram bot.
Perfect for "save for later" workflow — forward any message to your
bot and it gets ingested into the Wiki.

Setup:
  1. Create bot via @BotFather on Telegram
  2. Get token (e.g., 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)
  3. Set allowed_user_ids (your Telegram user ID)
  4. Start source — it will poll for new messages

Configuration:
    settings:
      bot_token: "123456789:ABC..."   # From @BotFather
      allowed_user_ids: [12345678]     # Only accept from these users
      include_forwarded: true          # Ingest forwarded messages too
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List

from .base import BaseSource, IngestItem, SourceConfig, SourceType, ContentType

logger = logging.getLogger("cw-source-telegram")


class TelegramBotSource(BaseSource):
    """Telegram bot that receives messages to ingest."""

    @property
    def source_type(self) -> SourceType:
        return SourceType.BOT

    @property
    def display_name(self) -> str:
        return "Telegram Bot"

    @property
    def description(self) -> str:
        return "Receive messages from a Telegram bot"

    async def start(self):
        await super().start()
        
        self._queue: List[IngestItem] = []
        self._token = self.config.settings.get("bot_token", "")
        self._allowed = set(self.config.settings.get("allowed_user_ids", []))
        self._offset = 0
        
        if not self._token:
            logger.warning("No bot_token configured — Telegram source disabled")
            return
        
        logger.info(f"🤖 Telegram bot started")
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
        """Long-poll Telegram API for updates."""
        while self._running:
            try:
                import aiohttp
                
                url = f"https://api.telegram.org/bot{self._token}/getUpdates"
                params = {"timeout": 30, "offset": self._offset}
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params) as resp:
                        data = await resp.json()
                
                if data.get("ok"):
                    for update in data.get("result", []):
                        self._offset = update["update_id"] + 1
                        msg = update.get("message", {})
                        
                        # Auth check
                        user_id = msg.get("from", {}).get("id")
                        if self._allowed and user_id not in self._allowed:
                            continue
                        
                        text = msg.get("text") or msg.get("caption", "")
                        if not text or len(text.strip()) < 5:
                            continue
                        
                        item = IngestItem(
                            content=text,
                            title=text[:80],
                            source_type=SourceType.BOT,
                            content_type=ContentType.NOTE,
                            metadata={
                                "chat_id": msg.get("chat", {}).get("id"),
                                "message_id": msg.get("message_id"),
                                "from": msg.get("from", {}).get("first_name", ""),
                                "forward_from": msg.get("forward_from", {}).get("first_name", ""),
                                "date": datetime.fromtimestamp(msg.get("date", 0)).isoformat(),
                            },
                            tags=["telegram"],
                        )
                        
                        if self.validate_item(item):
                            self._queue.append(item)
                            logger.info(f"🤖 TG: {text[:50]}...")
                
                else:
                    logger.error(f"TG API error: {data}")
                    
            except Exception as e:
                logger.debug(f"TG poll error: {e}")
                await asyncio.sleep(5)
