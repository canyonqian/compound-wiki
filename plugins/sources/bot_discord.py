"""
Discord Bot Source Plugin
=========================

Monitor Discord channels for messages to ingest.
Useful for saving interesting discussions, code snippets,
or links shared in your Discord servers.

Configuration:
    settings:
      bot_token: "your-discord-bot-token"
      channel_ids: [123456789]        # Only watch these channels
      include_attachments: true       # Save attached images/text
"""

import asyncio
import logging
from typing import Any, Dict, List

from .base import BaseSource, IngestItem, SourceConfig, SourceType, ContentType

logger = logging.getLogger("cw-source-discord")


class DiscordBotSource(BaseSource):
    """Discord channel monitor."""

    @property
    def source_type(self) -> SourceType:
        return SourceType.BOT

    @property
    def display_name(self) -> str:
        return "Discord Bot"

    @property
    def description(self) -> str:
        return "Monitor Discord channels for messages"

    async def start(self):
        await super().start()
        
        self._queue: List[IngestItem] = []
        self._token = self.config.settings.get("bot_token", "")
        self._channels = set(self.config.settings.get("channel_ids", []))
        
        if not self._token:
            logger.warning("No bot_token — Discord source disabled")
            return
        
        logger.info("💬 Discord bot started")
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
                import aiohttp
                
                # Get gateway info for websocket connection
                url = f"https://discord.com/api/v10/gateway/bot"
                headers = {"Authorization": f"Bot {self._token}"}
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers) as resp:
                        data = await resp.json()
                        ws_url = data.get("url")
                    
                    # Connect via WebSocket
                    from aiohttp import WSMsgType
                    async with session.ws_connect(f"{ws_url}?v=10&encoding=json") as ws:
                        # Send identify
                        await ws.send_json({
                            "op": 2,  # IDENTIFY
                            "d": {
                                "token": self._token,
                                "intents": 1 << 9,  # MESSAGE_CONTENT intent
                                "properties": {
                                    "os": "linux", "browser": "cw-wiki", "device": "cw-wiki",
                                },
                            }
                        })
                        
                        while self._running:
                            msg = await ws.receive()
                            if msg.type in (WSMsgType.CLOSED, WSMsgType.ERROR):
                                break
                            
                            data = msg.json if isinstance(msg.data, str) else {}
                            t = data.get("t")
                            d = data.get("d", {})
                            
                            # Handle message
                            if t == "MESSAGE_CREATE":
                                channel_id = d.get("channel_id", "")
                                if self._channels and channel_id not in [str(c) for c in self._channels]:
                                    continue
                                
                                content = d.get("content", "")
                                if len(content.strip()) < 5:
                                    continue
                                
                                item = IngestItem(
                                    content=content,
                                    title=content[:80],
                                    source_type=SourceType.BOT,
                                    content_type=ContentType.CONVERSATION,
                                    metadata={
                                        "channel_id": channel_id,
                                        "author": d.get("author", {}).get("username", ""),
                                        "message_id": d.get("id"),
                                        "guild_id": d.get("guild_id"),
                                    },
                                    tags=["discord"],
                                )
                                
                                if self.validate_item(item):
                                    self._queue.append(item)
                                    
            except Exception as e:
                logger.debug(f"Discord error: {e}")
                await asyncio.sleep(10)
