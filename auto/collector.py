"""
Compound Wiki - Web Collector
================================
Automatically fetches web content and saves it to raw/ for ingestion.
Supports: direct URLs, RSS feeds, bookmark files, batch URL lists.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("compound_wiki.collector")


class WebCollector:
    """
    Fetches web pages, extracts main content, saves to raw/collected/.
    
    Supports multiple input modes:
      - Single URL: collector.collect("https://example.com/article")
      - Multiple URLs: collector.collect(["url1", "url2", ...])
      - RSS feed: collector.from_rss("https://blog.example.com/rss")
      - Bookmark file: collector.from_bookmarks("bookmarks.html")
      - Text file with URLs (one per line): collector.from_file("urls.txt")
    """

    def __init__(self, config=None):
        self.config = config or {}
        self.output_dir = Path(self.config.get("output_dir", "raw/collected"))
        self.timeout = self.config.get("timeout_seconds", 30)
        self.max_content_length = self.config.get("max_content_length", 5 * 1024 * 1024)
        self.extract_main = self.config.get("extract_main_content", True)
        self.convert_to_md = self.config.get("convert_to_markdown", True)
        self.user_agent = self.config.get(
            "user_agent",
            "CompoundWiki-Bot/1.0 (Educational Research; +https://github.com/...)"
        )
        self.enabled = self.config.get("enabled", True)

        # Rate limiting
        self.rpm = self.config.get("requests_per_minute", 10)
        self._request_times: list[float] = []

        # Stats
        self.stats = {
            "total_fetched": 0,
            "total_saved": 0,
            "total_failed": 0,
            "total_bytes": 0,
        }

    def _rate_limit(self) -> None:
        """Enforce requests-per-minute limit."""
        now = time.time()
        self._request_times = [t for t in self._request_times if now - t < 60]
        if len(self._request_times) >= self.rpm:
            wait = 60 - (now - self._request_times[0]) + 0.5
            if wait > 0:
                logger.debug(f"Rate limiting: waiting {wait:.1f}s...")
                time.sleep(wait)
        self._request_times.append(now)

    def collect(self, urls: str | list[str]) -> list[dict]:
        """
        Main entry point. Collect one or more URLs.
        
        Returns list of result dicts with keys:
          url, status, saved_path, size, error (if failed)
        """
        if isinstance(urls, str):
            urls = [urls]

        if not self.enabled:
            logger.info("Collector disabled by configuration.")
            return []

        results = []
        total = len(urls)

        for i, url in enumerate(urls, 1):
            url = url.strip()
            if not url or url.startswith("#"):
                continue

            logger.info(f"🌐 [{i}/{total}] Fetching: {url[:80]}")
            self._rate_limit()

            try:
                result = self._fetch_one(url)
                results.append(result)

                if result["status"] == "ok":
                    logger.info(f"   ✅ Saved → {result['saved_path']} ({result['size']:,} bytes)")
                    self.stats["total_saved"] += 1
                else:
                    logger.warning(f"   ❌ Failed: {result['error']}")
                    self.stats["total_failed"] += 1

                self.stats["total_fetched"] += 1
                self.stats["total_bytes"] += result.get("size", 0)

            except Exception as e:
                logger.error(f"   ❌ Error fetching {url}: {e}")
                results.append({"url": url, "status": "error", "error": str(e), "saved_path": None, "size": 0})
                self.stats["total_failed"] += 1
                self.stats["total_fetched"] += 1

        logger.info(f"\n🌐 Collection complete: {self.stats['total_saved']} saved, {self.stats['total_failed']} failed")
        return results

    def _fetch_one(self, url: str) -> dict:
        """Fetch a single URL and save to disk."""
        import urllib.request
        import urllib.error
        from html.parser import HTMLParser

        # Make HTTP request
        req = urllib.request.Request(url, headers={
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,text/plain,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        })

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw_html = resp.read(self.max_content_length)
                content_type = resp.headers.get("Content-Type", "")
                final_url = resp.url  # Follow redirects

        except urllib.error.HTTPError as e:
            return {"url": url, "status": "error", "error": f"HTTP {e.code}: {e.reason}", "saved_path": None, "size": 0}
        except urllib.error.URLError as e:
            return {"url": url, "status": "error", "error": f"URL Error: {e.reason}", "saved_path": None, "size": 0}
        except Exception as e:
            return {"url": url, "status": "error", "error": str(e), "saved_path": None, "size": 0}

        # Process content based on type
        if b"text/html" in content_type.lower():
            text_content = self._html_to_text(raw_html.decode("utf-8", errors="replace"), url)
        elif b"text/plain" in content_type.lower() or b"text/markdown" in content_type.lower():
            text_content = raw_html.decode("utf-8", errors="replace")
        else:
            # Binary or unknown — save raw but warn
            text_content = f"[Binary/unknown content — saved raw]\n\nSource URL: {final_url}\nContent-Type: {content_type}"
            raw_html  # keep reference

        if not text_content.strip():
            return {"url": url, "status": "error", "error": "Empty content after extraction", "saved_path": None, "size": 0}

        # Generate safe filename
        filename = self._generate_filename(final_url)
        filepath = self.output_dir / filename

        # Add metadata header
        meta_header = f"""---
source_url: {final_url}
collected_at: {datetime.now().isoformat()}
collector: compound-wiki
---

# {self._title_from_url(final_url)}

> Collected by Compound Wiki on {datetime.now().strftime('%Y-%m-%d %H:%M')}
> Source: <{final_url}>

---
"""

        full_content = meta_header + text_content
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(full_content, encoding="utf-8")

        return {
            "url": url,
            "status": "ok",
            "saved_path": str(filepath),
            "size": len(full_content.encode("utf-8")),
        }

    @staticmethod
    def _html_to_text(html: str, base_url: str) -> str:
        """Extract readable text from HTML."""
        
        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.result = []
                self.in_body = False
                self.skip_tags = {"script", "style", "nav", "footer", "header"}
                self.current_skip = None
                
            def handle_starttag(self, tag, attrs):
                tag_lower = tag.lower()
                if tag_lower == "body":
                    self.in_body = True
                if tag_lower in self.skip_tags:
                    self.current_skip = tag_lower
                if tag_lower in ("p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"):
                    if self.current_skip is None:
                        self.result.append("\n")
                if tag_lower in ("h1", "h2") and self.current_skip is None:
                    self.result.append("\n## ")
            
            def handle_endtag(self, tag):
                if tag.lower() == self.current_skip:
                    self.current_skip = None
            
            def handle_data(self, data):
                if self.in_body and self.current_skip is None:
                    stripped = data.strip()
                    if stripped:
                        self.result.append(stripped)
        
        extractor = TextExtractor()
        try:
            extractor.feed(html)
        text = "".join(extractor.result)
        # Clean up excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        return text
        except Exception:
            # Fallback: strip tags naively
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s{2,}', '\n', text).strip()
            return text

    def _generate_filename(self, url: str) -> str:
        """Generate a safe filename from URL."""
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        domain = parsed.netloc.replace(".", "-")
        path = parsed.path.rstrip("/").replace("/", "-")[:60] or "index"
        
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        hash_suffix = hashlib.md5(url.encode()).hexdigest()[:6]
        
        clean_name = re.sub(r'[^a-zA-Z0-9\-_]', '-', f"{domain}-{path}")[:80]
        return f"{ts}-{clean_name}-{hash_suffix}.md"

    @staticmethod
    def _title_from_url(url: str) -> str:
        """Try to extract a title from URL path."""
        from urllib.parse import urlparse
        path = urlparse(url).path.rstrip("/")
        if not path:
            return "Untitled"
        name = path.split("/")[-1]
        return name.replace("-", " ").replace("_", " ").title() or "Untitled"

    # ── Bulk collection methods ────────────────────────────

    def from_rss(self, rss_url: str, max_items: int = 20) -> list[dict]:
        """Collect items from an RSS/Atom feed."""
        import urllib.request
        
        logger.info(f"📡 Fetching RSS feed: {rss_url}")
        req = urllib.request.Request(rss_url, headers={"User-Agent": self.user_agent})
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                rss_xml = resp.read()
        except Exception as e:
            logger.error(f"Failed to fetch RSS: {e}")
            return []

        # Parse RSS without requiring feedparser
        urls = self._extract_urls_from_rss(rss_xml.decode("utf-8", errors="replace"))
        urls = urls[:max_items]

        logger.info(f"Found {len(urls)} items in feed.")
        return self.collect(urls)

    def from_bookmarks(self, bookmarks_file: str) -> list[dict]:
        """Collect URLs from a browser bookmarks export (HTML format)."""
        bp = Path(bookmarks_file)
        if not bp.exists():
            logger.error(f"Bookmarks file not found: {bp}")
            return []

        html = bp.read_text(encoding="utf-8", errors="replace")
        urls = re.findall(r'HREF="(https?://[^"]+)"', html, re.IGNORECASE)
        
        logger.info(f"Found {len(urls)} bookmarks in {bookmarks_file}")
        return self.collect(urls)

    def from_file(self, url_list_file: str) -> list[dict]:
        """Read URLs from a text file (one per line, # comments OK)."""
        p = Path(url_list_file)
        if not p.exists():
            logger.error(f"URL list file not found: {p}")
            return []

        lines = p.read_text(encoding="utf-8").splitlines()
        urls = [
            line.strip().split()[0]  # Take first word (URL), ignore extra fields
            for line in lines
            if line.strip() and not line.strip().startswith("#")
        ]

        logger.info(f"Found {len(urls)} URLs in {url_list_file}")
        return self.collect(urls)

    def from_clipboard(self) -> list[dict]:
        """Try to read URL from clipboard (platform-dependent)."""
        try:
            import subprocess
            
            if os.name == "nt":
                result = subprocess.run(["powershell", "-command", "Get-Clipboard"], capture_output=True, text=True)
                text = result.stdout.strip()
            else:
                import subprocess
                result = subprocess.run(["xclip", "-selection", "clipboard", "-o"], capture_output=True, text=True)
                text = result.stdout.strip()
            
            if text.startswith(("http://", "https://")):
                logger.info(f"📋 Found URL in clipboard: {text[:80]}")
                return self.collect(text)
            else:
                logger.info("Clipboard does not contain a URL.")
                return []
                
        except Exception as e:
            logger.debug(f"Clipboard access unavailable: {e}")
            return []

    @staticmethod
    def _extract_urls_from_rss(xml_text: str) -> list[str]:
        """Extract link URLs from RSS/Atom XML without external deps."""
        # Try <link> tags first
        links = re.findall(r'<link[^>]*href=["\']?(https?://[^"\'\s>]+)', xml_text, re.IGNORECASE)
        
        # Also try <guid> tags
        guids = re.findall(r'<guid[^>]*>(https?://[^<]+)</guid>', xml_text, re.IGNORECASE)
        
        all_urls = links + guids
        
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for u in all_urls:
            if u not in seen:
                seen.add(u)
                unique.append(u)
        
        return unique

    def get_stats(self) -> dict:
        return dict(self.stats)


# Import here for Windows compatibility
import os