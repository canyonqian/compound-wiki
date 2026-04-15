"""
Browser Extension Source Plugin (Enhanced)
==========================================

Smart web clipper with TWO modes:

  1. **Bookmarklet** — Manual "click to save" (legacy mode)
     Drag bookmarklet to bookmarks bar → click on any page

  2. **Smart Auto-Capture** ⭐ — Fully automatic (NEW!)
     Browser extension analyzes page quality + reading behavior
     Auto-saves when score exceeds threshold — NO user action needed

Endpoints:
  POST /clip          ← Bookmarklet manual save
  POST /auto-clip     ← Smart extension auto-capture
  GET  /bookmarklet.js ← Bookmarklet install page

Auto-capture pipeline:
  Extension detects valuable content
    → POST /auto-clip with full analysis data
    → Server validates & enriches
    → Saves to raw/ with metadata
    → Triggers INGEST pipeline automatically
    → Wiki pages generated

Configuration:
    sources:
      browser:
        enabled: true
        settings:
          port: 9877
          auto_ingest: true           # Auto-trigger INGEST after capture
          auto_clip_max_size: 5MB     # Max payload size
          default_tags: []            # Default tags for all captures
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import BaseSource, IngestItem, SourceConfig, SourceType, ContentType

logger = logging.getLogger("cw-source-browser")


class BrowserClipperSource(BaseSource):
    """
    Enhanced browser clipper supporting both manual bookmarklet
    and smart extension auto-capture.
    """

    @property
    def source_type(self) -> SourceType:
        return SourceType.BROWSER

    @property
    def display_name(self) -> str:
        return "Browser Clipper (Smart)"

    @property
    def description(self) -> str:
        return "Smart browser extension + bookmarklet for automatic web capture"

    async def start(self):
        await super().start()
        
        self._queue: List[IngestItem] = []
        self._port = self.config.settings.get("port", 9877)
        self._auto_ingest = self.config.settings.get("auto_ingest", True)
        self._capture_count = 0
        self._recent_captures: List[Dict] = []
        
        logger.info(f"🌐 Smart browser clipper starting (port={self._port})")
        
        try:
            from aiohttp import web
            
            app = web.Application(client_max_size=50 * 1024 * 1024)
            
            # Legacy bookmarklet endpoint
            app.router.add_post("/clip", self._handle_clip)
            
            # ⭐ Smart auto-capture endpoint (NEW)
            app.router.add_post("/auto-clip", self._handle_auto_clip)
            
            # Bookmarklet installer page
            app.router.add_get("/bookmarklet.js", self._serve_bookmarklet)
            
            # Status API (for popup to check connection)
            app.router.add_get("/status", self._handle_status)
            
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "127.0.0.1", self._port)
            await site.start()
            self._server = runner
            
            print(f"""
╔══════════════════════════════════════════════════════╗
║  🌐 Smart Browser Clipper Ready                      ║
║                                                      ║
║  📌 Bookmarklet:                                     ║
║     http://localhost:{self._port}/bookmarklet.js         ║
║                                                      ║
║  🔌 Extension Endpoint:                              ║
║     POST http://localhost:{self._port}/auto-clip       ║
║                                                      ║
║  📊 Status:                                          ║
║     GET  http://localhost:{self._port}/status          ║
║                                                      ║
║  Modes:                                              ║
║     • Bookmarklet (manual click)                     ║
║     • Smart Extension (fully automatic!)             ║
╚══════════════════════════════════════════════════════╝
""")
            
        except ImportError:
            logger.warning("aiohttp not installed — browser clipper unavailable")

    async def stop(self):
        if hasattr(self, '_server'):
            await self._server.cleanup()
        await super().stop()

    async def collect(self) -> List[IngestItem]:
        items = list(self._queue)
        self._queue.clear()
        return items

    # ================================================================
    # LEGACY: Manual Bookmarklet Handler
    # ================================================================

    async def _handle_clip(self, request):
        """Handle manual bookmarklet clip request."""
        try:
            data = await request.json()
            
            item = IngestItem(
                content=data.get("content", ""),
                title=data.get("title") or data.get("url", ""),
                url=data.get("url", ""),
                source_type=SourceType.BROWSER,
                content_type=ContentType.ARTICLE,
                metadata={
                    "method": "bookmarklet",
                    "user_agent": request.headers.get("User-Agent", ""),
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                },
                tags=["web-clip", "manual"],
            )
            
            if self.validate_item(item):
                self._queue.append(item)
                self._capture_count += 1
                
            from aiohttp import web
            return web.json_response({"ok": True, "title": item.title})
            
        except Exception as e:
            from aiohttp import web
            logger.error(f"Clip error: {e}")
            return web.json_response({"ok": False, "error": str(e)}, status=400)

    # ================================================================
    # NEW: Smart Auto-Capture Handler
    # ================================================================

    async def _handle_auto_clip(self, request):
        """
        Handle smart extension auto-capture.
        
        The browser extension has already:
        1. Analyzed page content (density, length, structure)
        2. Tracked user behavior (scroll depth, dwell time, highlights)
        3. Computed a value score (6 dimensions)
        4. Extracted clean article text (Readability algorithm)
        5. Classified content type and generated tags
        
        Our job here:
        1. Receive and validate the payload
        2. Enrich with server-side metadata
        3. Save to raw/ with full metadata JSON
        4. Queue for INGEST pipeline processing
        5. Return confirmation with wiki page reference
        """
        from aiohttp import web
        
        try:
            raw_data = await request.json()
            
            # Validate required fields
            if not raw_data.get("url") or not raw_data.get("content"):
                return web.json_response(
                    {"ok": False, "error": "Missing url or content"},
                    status=400
                )
            
            # Build enriched ingest item
            capture_id = f"auto-{int(time.time() * 1000)}"
            
            # Merge extension-provided metadata with our own
            metadata = {
                "method": "smart_extension",
                "capture_id": capture_id,
                
                # Extension's scoring data
                "score": raw_data.get("score", 0),
                "trigger": raw_data.get("trigger", "unknown"),
                "dimensions": raw_data.get("dimensions", {}),
                
                # Reading behavior
                "behavior": raw_data.get("behavior", {}),
                
                # Content classification
                "content_type_ext": raw_data.get("contentType", "general"),
                "tags_ext": raw_data.get("tags", []),
                
                # Article metadata
                "author": raw_data.get("author", ""),
                "publish_date": raw_data.get("publishDate", ""),
                "word_count": raw_data.get("wordCount", 0),
                "estimated_read_time": raw_data.get("estimatedReadTime", 0),
                
                # Server-side metadata
                "received_at": datetime.now(timezone.utc).isoformat(),
                "source_agent": request.headers.get("X-Source", "unknown"),
                "extension_version": request.headers.get("X-Version", "unknown"),
                "user_agent": request.headers.get("User-Agent", ""),
                
                # Raw excerpt for preview
                "excerpt": raw_data.get("excerpt", "")[:500],
            }
            
            # Determine content type from extension classification
            content_type = self._map_content_type(raw_data.get("contentType"))
            
            item = IngestItem(
                content=raw_data.get("content", ""),
                title=raw_data.get("title") or raw_data.get("url", ""),
                url=raw_data.get("url", ""),
                source_type=SourceType.BROWSER,
                content_type=content_type,
                metadata=metadata,
                tags=self._build_tags(raw_data),
            )
            
            if self.validate_item(item):
                # Save to disk (raw/ directory)
                file_path = self._save_to_raw(item, capture_id)
                
                # Add to queue for INGEST pipeline
                self._queue.append(item)
                
                # Track recent captures (for popup display)
                self._track_capture(raw_data, capture_id)
                
                self._capture_count += 1
                
                logger.info(
                    f"🧠 Auto-captured [{raw_data.get('trigger')}] "
                    f"(score={raw_data.get('score')}): {item.title}"
                )
                
                return web.json_response({
                    "ok": True,
                    "capture_id": capture_id,
                    "title": item.title,
                    "score": raw_data.get("score", 0),
                    "saved_to": str(file_path) if file_path else None,
                    "queued_for_ingest": self._auto_ingest,
                    "message": (
                        f"✅ Captured! Score: {raw_data.get('score')}/100"
                        f" · Trigger: {raw_data.get('trigger', 'unknown')}"
                        ),
                })
            else:
                return web.json_response({
                    "ok": False,
                    "error": "Content validation failed",
                    "reason": "Content too short or empty"
                }, status=400)
                
        except json.JSONDecodeError:
            return web.json_response(
                {"ok": False, "error": "Invalid JSON payload"}, 
                status=400
            )
        except Exception as e:
            logger.error(f"Auto-clip error: {e}", exc_info=True)
            return web.json_response(
                {"ok": False, "error": str(e)}, 
                status=500
            )

    def _map_content_type(self, ext_type: str) -> ContentType:
        """Map extension content type to internal ContentType enum."""
        mapping = {
            "paper": ContentType.PAPER,
            "article": ContentType.ARTICLE,
            "blog": ContentType.ARTICLE,
            "tutorial": ContentType.TUTORIAL,
            "news": ContentType.NEWS,
            "code": ContentType.CODE,
            "video": ContentType.MEDIA,
            "book": ContentType.BOOK,
            "doc": ContentType.DOCUMENT,
            "general": ContentType.ARTICLE,
        }
        return mapping.get(ext_type.lower(), ContentType.ARTICLE)

    def _build_tags(self, raw_data: Dict) -> List[str]:
        """Build comprehensive tag list from capture data."""
        tags = set(["web-clip", "auto"])
        
        # Extension-generated tags
        ext_tags = raw_data.get("tags", [])
        if isinstance(ext_tags, list):
            tags.update(ext_tags)
        
        # Content type
        ct = raw_data.get("contentType", "")
        if ct:
            tags.add(ct)
        
        # Quality-based
        score = raw_data.get("score", 0)
        if score >= 85:
            tags.add("high-quality")
        elif score >= 70:
            tags.add("good-quality")
        
        # Trigger-based
        trigger = raw_data.get("trigger", "")
        if "high_confidence" in trigger:
            tags.add("auto-high-confidence")
        elif "page_leave" in trigger or "page_unload" in trigger:
            tags.add("auto-on-exit")
        
        # User-configured default tags
        defaults = self.config.settings.get("default_tags", [])
        if isinstance(defaults, list):
            tags.update(defaults)
        
        return list(tags)[:15]

    def _save_to_raw(self, item: IngestItem, capture_id: str) -> Optional[Path]:
        """Save captured content to raw/ directory with full metadata."""
        try:
            project_dir = Path(self.config.project_dir or ".")
            raw_dir = project_dir / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate safe filename
            safe_title = "".join(
                c for c in (item.title or "untitled")[:80]
                if c.isalnum() or c in (" ", "-", "_")
            ).strip().replace(" ", "-") or "untitled"
            
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            filename = f"{timestamp}-{safe_title}.md"
            file_path = raw_dir / filename
            
            # Write markdown with frontmatter metadata
            frontmatter = {
                "source": "browser-extension-auto",
                "capture_id": capture_id,
                "original_url": item.url,
                "title": item.title,
                "author": item.metadata.get("author", ""),
                "published_date": item.metadata.get("publish_date", ""),
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "score": item.metadata.get("score", 0),
                "trigger": item.metadata.get("trigger", ""),
                "tags": item.tags,
                "word_count": item.metadata.get("word_count", 0),
                "read_time_min": item.metadata.get("estimated_read_time", 0),
                "behavior": item.metadata.get("behavior", {}),
                "dimensions": item.metadata.get("dimensions", {}),
            }
            
            # Format frontmatter as YAML-like block
            fm_lines = ["---"]
            for k, v in frontmatter.items():
                if isinstance(v, dict):
                    fm_lines.append(f"  {k}: {json.dumps(v)}")
                elif isinstance(v, list):
                    fm_lines.append(f"  {k}: {json.dumps(v)}")
                elif v:
                    fm_lines.append(f"  {k}: {v}")
            fm_lines.append("---")
            
            md_content = "\n".join(fm_lines) + "\n\n" + item.content + "\n"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            logger.debug(f"Saved auto-capture to {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Failed to save to raw/: {e}", exc_info=True)
            return None

    def _track_capture(self, raw_data: Dict, capture_id: str):
        """Keep a recent captures log for popup display."""
        entry = {
            "id": capture_id,
            "title": raw_data.get("title", "")[:100],
            "score": raw_data.get("score", 0),
            "trigger": raw_data.get("trigger", ""),
            "time": time.time(),
        }
        
        self._recent_captures.insert(0, entry)
        if len(self._recent_captures) > 20:
            self._recent_captures = self._recent_captures[:20]

    # ================================================================
    # STATUS ENDPOINT
    # ================================================================

    async def _handle_status(self, request):
        """Return server status for popup connection check."""
        from aiohttp import web
        
        return web.json_response({
            "status": "running",
            "version": "1.2.0",
            "port": self._port,
            "total_captures": self._capture_count,
            "auto_ingest": self._auto_ingest,
            "recent": [
                {**c, "time_ago": f"{int(time.time() - c['time'])}s ago"}
                for c in self._recent_captures[:10]
            ],
        })

    # ================================================================
    # BOOKMARKLET SERVE (unchanged from original)
    # ================================================================

    async def _serve_bookmarklet(self, request):
        """Serve the bookmarklet JavaScript installer page."""
        port = self._port
        
        js_code = f'''(function() {{
    var d=document,w=window,e=encodeURIComponent;
    var t=d.title,u=location.href;
    
    var c="";
    var sel=window.getSelection();
    if(sel.rangeCount>0) c=sel.toString();
    if(!c && d.body) c=d.body.innerText.substring(0,50000);
    
    fetch('http://localhost:{port}/clip', {{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify({{title:t,url:u,content:c}})
    }}).then(function(r){{
        if(r.ok) alert('\\u2705 Saved to CAM: '+t);
        else alert('\\u274C Save failed');
    }}).catch(function(e){{
        alert('\\u274C Cannot reach Wiki server. Is it running?');
    }});
}})();
// CAM Clipper'''

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>CAM — Bookmarklet</title>
<style>body{{font-family:-apple-system,sans-serif;max-width:600px;margin:50px auto;padding:20px}}
a.clip{{display:inline-block;background:#2563eb;color:#fff;padding:12px 24px;
border-radius:8px;text-decoration:none;font-size:16px;font-weight:bold}}
a.clip:hover{{background:#1d4ed8}}code{{background:#f1f5f9;padding:2px 6px;border-radius:4px}}</style></head>
<body>
<h1>\\ud83e\\udde0 CAM \\u2014 Browser Clipper</h1>
<p>Drag this button to your browser's bookmarks bar:</p>
<a class="clip" href="javascript:{e(js_code)}">\\ud83d\\udcce Save to Wiki</a>
<h2>How to use</h2><ol>
<li>Drag the <b>\\ud83d\\udcce Save to Wiki</b> button above to your bookmarks bar</li>
<li>Navigate to any article/webpage you want to save</li>
<li>Click the <b>\\ud83d\\udcce Save to Wiki</b> bookmark</li>
<li>The page is automatically sent to your CAM!</li>
</ol>
<p><b>TIP:</b> Select/highlight text first, and only the selection will be saved.</p>

<hr style="margin:24px 0;border:none;border-top:1px solid #e2e8f0">
<h2>\\u26a1\\ufe0f Or: Install Smart Extension (Recommended)</h2>
<p>The smart extension <b>automatically saves articles</b> based on your reading behavior \u2014 no clicking needed!</p>
<p>To install the smart extension, see <code>plugins/browser-extension/README.md</code>.</p>
</body></html>"""

        from aiohttp import web
        return web.Response(text=html, content_type="text/html; charset=utf-8")

    def get_recent_captures(self) -> List[Dict]:
        """Return recent captures for display purposes."""
        return list(self._recent_captures)

    def get_stats(self) -> Dict[str, Any]:
        """Return statistics about this source."""
        return {
            "total_captures": self._capture_count,
            "queue_size": len(self._queue),
            "recent_captures": len(self._recent_captures),
            "port": self._port,
            "auto_ingest_enabled": self._auto_ingest,
        }
