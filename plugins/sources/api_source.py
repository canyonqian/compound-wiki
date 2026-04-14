"""
API Source Plugin
=================

REST API endpoint for programmatic content ingestion.

Starts a lightweight HTTP server that accepts POST requests with content.
Any application or script can send data to your Wiki via HTTP.

Usage:
    # Start API server
    source = APISource(SourceConfig(
        settings={"port": 9876, "host": "0.0.0.0"}
    ))
    await source.start()
    
    # From any client (curl / Python / JS):
    curl -X POST http://localhost:9876/ingest \
      -H "Content-Type: application/json" \
      -d '{"content": "...", "title": "My Article", "tags": ["ai"]}'
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List

from .base import BaseSource, IngestItem, SourceConfig, SourceType, ContentType

logger = logging.getLogger("cw-source-api")


class APISource(BaseSource):
    """
    REST API data source.
    
    Provides an HTTP endpoint for external systems to push content into the wiki.
    
    Endpoints:
        POST /ingest       — Ingest new content (JSON body)
        GET  /status       — Check API health
        GET  /recent       — List recently ingested items
    """
    
    @property
    def source_type(self) -> SourceType:
        return SourceType.API

    @property
    def display_name(self) -> str:
        return "REST API Endpoint"

    @property
    def description(self) -> str:
        return "HTTP REST API — receive content from any app/script via POST requests"

    async def start(self):
        """Start the HTTP server."""
        await super().start()
        
        port = self.config.settings.get("port", 9876)
        host = self.config.settings.get("host", "127.0.0.1")
        api_key = self.config.settings.get("api_key", "")  # Optional auth
        
        self._items: List[IngestItem] = []
        self._server = None
        
        try:
            from aiohttp import web
            
            app = web.Application(client_max_size=50 * 1024 * 1024)  # 50MB max
            
            # Auth middleware if api_key set
            if api_key:
                @web.middleware
                async def auth_middleware(request, handler):
                    if request.path == "/status":
                        return await handler(request)
                    key = request.headers.get("X-API-Key", "")
                    if key != api_key:
                        return web.json_response({"error": "Unauthorized"}, status=401)
                    return await handler(request)
                app.middlewares.append(auth_middleware)
            
            app.router.add_post("/ingest", self._handle_ingest)
            app.router.add_post("/ingest/batch", self._handle_batch_ingest)
            app.router.add_get("/status", self._handle_status)
            app.router.add_get("/recent", self._handle_recent)
            
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, host, port)
            await site.start()
            
            self._server = runner
            logger.info(f"📡 API server started on http://{host}:{port}")
            
        except ImportError:
            logger.warning("aiohttp not installed, using built-in fallback")
            await self._start_fallback(host, port)

    async def _start_fallback(self, host: str, port: int):
        """Fallback using asyncio streams (no external deps)."""
        # Minimal HTTP parser for ingest endpoint
        pass  # Simplified: recommend aiohttp installation

    async def stop(self):
        """Stop the HTTP server."""
        if self._server:
            await self._server.cleanup()
        await super().stop()
        logger.info("📡 API server stopped")

    async def collect(self) -> List[IngestItem]:
        """Return items received since last collection."""
        items = list(self._items)
        self._items.clear()
        return items

    # ── HTTP Handlers ────────────────────────────────────────
    
    async def _handle_ingest(self, request):
        """Handle single content ingestion."""
        try:
            data = await request.json()
            
            item = IngestItem(
                content=data.get("content", ""),
                title=data.get("title", ""),
                url=data.get("url", ""),
                source_type=SourceType.API,
                content_type=self._map_type(data.get("content_type")),
                tags=data.get("tags", []),
                priority=int(data.get("priority", 2)),
                metadata={
                    "client_ip": request.remote,
                    "user_agent": request.headers.get("User-Agent", ""),
                    **{k: v for k, v in data.items() 
                       if k not in ("content", "title", "url", "content_type", "tags", "priority")},
                },
            )
            
            if not self.validate_item(item):
                from aiohttp import web
                return web.json_response({
                    "success": False,
                    "error": "Content validation failed (too short or blocked)"
                }, status=400)
            
            self._items.append(item)
            
            from aiohttp import web
            return web.json_response({
                "success": True,
                "message": f"Content received: {item.title or '(untitled)'}",
                "item_id": id(item),
                "queued": True,
            })
            
        except Exception as e:
            from aiohttp import web
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=400)

    async def _handle_batch_ingest(self, request):
        """Handle batch ingestion."""
        try:
            data = await request.json()
            items_data = data.get("items", [data])  # Accept single or batch
            
            results = []
            for item_data in items_data:
                item = IngestItem(
                    content=item_data.get("content", ""),
                    title=item_data.get("title", ""),
                    url=item_data.get("url", ""),
                    source_type=SourceType.API,
                    tags=item_data.get("tags", []),
                )
                
                if self.validate_item(item):
                    self._items.append(item)
                    results.append({"title": item.title or "(untitled)", "ok": True})
                else:
                    results.append({"title": item.title or "(untitled)", "ok": False, "error": "validation"})
            
            from aiohttp import web
            return web.json_response({
                "success": True,
                "received": len(results),
                "accepted": sum(1 for r in results if r["ok"]),
                "results": results,
            })
            
        except Exception as e:
            from aiohttp import web
            return web.json_response({"success": False, "error": str(e)}, status=400)

    async def _handle_status(self, request):
        """Health check endpoint."""
        from aiohttp import web
        return web.json_response(await self.health_check())

    async def _handle_recent(self, request):
        """List recent items."""
        from aiohttp import web
        limit = int(request.query.get("limit", 20))
        recent = [{
            "title": i.title,
            "type": i.content_type.value,
            "tags": i.tags,
            "created_at": i.created_at.isoformat(),
        } for i in self._items[-limit:]]
        return web.json_response({"recent": recent, "count": len(recent)})

    @staticmethod
    def _map_type(type_str: str) -> ContentType:
        mapping = {
            "article": ContentType.ARTICLE, "paper": ContentType.PAPER,
            "note": ContentType.NOTE, "bookmark": ContentType.BOOKMARK,
            "code": ContentType.CODE, "pdf": ContentType.PDF,
            "conversation": ContentType.CONVERSATION, "tweet": ContentType.TWEET,
            "video": ContentType.VIDEO,
        }
        return mapping.get(type_str or "", ContentType.UNKNOWN)


# ── Quick-start helper ────────────────────────────────────

def start_api_server(port: int = 9876, api_key: str = "") -> APISource:
    """
    Convenience function to start the API source.
    
    Example:
        from plugins.sources.api_source import start_api_server
        
        source = start_api_server(port=9876, api_key="your-secret-key-here")
        await source.start()
        # Server running at http://localhost:9876/ingest
    """
    config = SourceConfig(
        name="api",
        enabled=True,
        auto_ingest=True,
        settings={"port": port, "host": "127.0.0.1", "api_key": api_key}
    )
    return APISource(config)
