"""
Webhook Source Plugin
=====================

Receive incoming webhooks from external services.
Integrates with Zapier, IFTTT, n8n, Make (Integromat), GitHub Actions, etc.

Setup examples:
  • Zapier: Webhook action → POST to http://localhost:9878/webhook
  • IFTTT: Webhooks service → POST to http://localhost:9878/webhook
  • n8n: HTTP Request node → POST to http://localhost:9878/webhook
  • GitHub Actions: curl -X POST .../webhook

Configuration:
    settings:
      port: 9878
      secret: "your-webhook-secret"   # Optional HMAC verification
      endpoints:
        zapier: "/webhook/zapier"
        ifttt: "/webhook/ifttt"
        github: "/webhook/github"
"""

import asyncio
import hashlib
import hmac
import logging
from typing import Any, Dict, List

from .base import BaseSource, IngestItem, SourceConfig, SourceType, ContentType

logger = logging.getLogger("cw-source-webhook")


class WebhookSource(BaseSource):
    """Incoming webhook receiver."""

    @property
    def source_type(self) -> SourceType:
        return SourceType.WEBHOOK

    @property
    def display_name(self) -> str:
        return "Webhook Receiver"

    @property
    def description(self) -> str:
        return "Receive webhooks from Zapier/IFTTT/n8n/GitHub/etc."

    async def start(self):
        await super().start()
        
        self._queue: List[IngestItem] = []
        self._port = self.config.settings.get("port", 9878)
        self._secret = self.config.settings.get("secret", "")
        
        logger.info(f"🪝 Webhook receiver started (port={self._port})")
        
        try:
            from aiohttp import web
            
            app = web.Application(client_max_size=10 * 1024 * 1024)
            
            # Generic endpoint + named endpoints
            endpoints = self.config.settings.get("endpoints", {})
            for name, path in endpoints.items():
                app.router.add_post(path or f"/webhook/{name}", self._make_handler(name))
            
            # Default catch-all
            app.router.add_post("/webhook", self._handle_webhook)
            app.router.add_get("/webhook/status", self._handle_status)
            
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "127.0.0.1", self._port)
            await site.start()
            self._server = runner
            
        except ImportError:
            logger.warning("aiohttp not installed")

    async def stop(self):
        if hasattr(self, '_server'):
            await self._server.cleanup()
        await super().stop()

    async def collect(self) -> List[IngestItem]:
        items = list(self._queue)
        self._queue.clear()
        return items

    def _make_handler(self, source_name: str):
        """Create a handler for a named endpoint."""
        async def handler(request):
            return await self._handle_webhook(request, source_name)
        return handler

    async def _handle_webhook(self, request, source_name: str = "default"):
        """Process incoming webhook."""
        try:
            # Verify HMAC if secret configured
            if self._secret:
                sig = request.headers.get("X-Webhook-Signature", "")
                body = await request.read()
                expected = hmac.new(
                    self._secret.encode(), body, hashlib.sha256
                ).hexdigest()
                if not hmac.compare_digest(sig, f"sha256={expected}"):
                    from aiohttp import web
                    return web.json_response({"error": "Invalid signature"}, status=403)
                data = json.loads(body)
            else:
                data = await request.json()
            
            # Extract content from various formats
            content, title = self._extract_content(data, source_name)
            
            item = IngestItem(
                content=content,
                title=title,
                source_type=SourceType.WEBHOOK,
                metadata={
                    "source": source_name,
                    "headers": dict(request.headers),
                    "raw_payload": data,
                },
                tags=["webhook", source_name],
            )
            
            if self.validate_item(item):
                self._queue.append(item)
                logger.info(f"🪝 Webhook [{source_name}]: {title[:50]}")
            
            from aiohttp import web
            return web.json_response({"ok": True})
            
        except Exception as e:
            from aiohttp import web
            return web.json_response({"ok": False, "error": str(e)}, status=400)

    async def _handle_status(self, request):
        from aiohttp import web
        return web.json_response({
            "status": "running",
            "sources": list(self.config.settings.get("endpaces", {}).keys()) + ["default"],
        })

    @staticmethod
    def _extract_content(data: Dict, source_name: str) -> tuple:
        """Extract content+title from various webhook formats."""
        
        # Zapier format
        if "content" in data:
            return data["content"], data.get("title", "")
        
        # IFTTT format  
        if "Value1" in data:
            parts = [data.get(f"Value{i}", "") for i in range(1, 4)]
            content = "\n".join(p for p in parts if p)
            return content, data.get("Value1", "")[:80]
        
        # Generic: use all string values
        title = data.get("title") or data.get("subject") or data.get("name") or ""
        
        # Build content from payload
        lines = []
        for k, v in data.items():
            if k.lower() not in ("title", "name", "subject"):
                v_str = str(v)
                if len(v_str) > 20 and not v_str.startswith("{") and not v_str.startswith("["):
                    lines.append(f"**{k}:** {v_str}")
        
        content = "\n".join(lines) if lines else str(data)
        return content, title


import json  # For _handle_webhook
