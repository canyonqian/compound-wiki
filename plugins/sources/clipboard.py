"""
Clipboard Source Plugin
=======================

Monitor system clipboard for text content.
When you copy text (article, note, code snippet), it's automatically
captured and queued for Wiki ingestion.

Platform Support:
  • macOS:   via AppKit (pyobjc) or pbpaste
  • Linux:  via xclip / xsel / wl-copy
  • Windows: via win32clipboard

Usage:
    source = ClipboardSource()
    await source.start()  # Starts monitoring clipboard every 2s
    
    # Now when user copies text, it appears in collect():
    items = await source.collect()  # Returns new copied content

Configuration:
    settings:
      - poll_interval: seconds between checks (default: 2)
      - min_length: minimum characters to capture (default: 50)
      - debounce_ms: ignore rapid copies (default: 3000)
"""

import asyncio
import logging
import platform
from datetime import datetime
from typing import Any, Dict, List

from .base import BaseSource, IngestItem, SourceConfig, SourceType, ContentType

logger = logging.getLogger("cw-source-clipboard")


class ClipboardSource(BaseSource):
    """
    System clipboard monitor.
    
    Continuously checks for new clipboard content and creates
    IngestItems from any substantial text that appears.
    
    Features:
      - Debouncing: ignores rapid successive copies
      - Deduplication: doesn't re-ingest same content  
      - Min length filter: ignores short copies (passwords, etc.)
    """

    @property
    def source_type(self) -> SourceType:
        return SourceType.CLIPBOARD

    @property
    def display_name(self) -> str:
        return "Clipboard Monitor"

    @property
    def description(self) -> str:
        return "Automatically captures text from system clipboard"

    async def start(self):
        """Start clipboard monitoring."""
        await super().start()
        
        self._last_content = ""
        self._last_copy_time: float = 0
        self._queue: List[IngestItem] = []
        
        interval = self.config.settings.get("poll_interval", 2)
        self._min_length = self.config.settings.get("min_length", 50)
        debounce = self.config.settings.get("debounce_ms", 3000)
        
        logger.info(f"📋 Clipboard monitor started (interval={interval}s, min={self._min_length} chars)")
        
        # Start background polling task
        self._task = asyncio.create_task(
            self._poll_loop(interval, debounce / 1000)
        )

    async def stop(self):
        """Stop monitoring."""
        if hasattr(self, '_task') and self._task:
            self._task.cancel()
        await super().stop()
        logger.info("📋 Clipboard monitor stopped")

    async def collect(self) -> List[IngestItem]:
        """Return newly captured clipboard content."""
        items = list(self._queue)
        self._queue.clear()
        return items

    async def health_check(self) -> Dict[str, Any]:
        base = await super().health_check()
        base["platform"] = platform.system()
        base["last_copied"] = bool(self._last_content)
        return base

    # ── Polling Loop ────────────────────────────────────────

    async def _poll_loop(self, interval: float, debounce: float):
        """Background loop that polls clipboard."""
        while self._running:
            try:
                current = self._read_clipboard()
                
                if current and len(current) >= self._min_length:
                    # Check dedup + debounce
                    now = asyncio.get_event_loop().time()
                    
                    if (
                        current != self._last_content 
                        and (now - self._last_copy_time) > debounce
                    ):
                        self._last_content = current
                        self._last_copy_time = now
                        
                        # Auto-detect content type
                        ct = self._detect_type(current)
                        
                        item = IngestItem(
                            content=current,
                            title=self._extract_title(current),
                            source_type=SourceType.CLIPBOARD,
                            content_type=ct,
                            metadata={"capture_method": "clipboard_poll"},
                        )
                        if self.validate_item(item):
                            self._queue.append(item)
                            logger.info(f"📋 Captured {len(current)} chars ({ct.value})")
                            
            except Exception as e:
                logger.debug(f"Clipboard read error: {e}")
            
            await asyncio.sleep(interval)

    def _read_clipboard(self) -> str:
        """
        Read system clipboard content.
        Platform-specific implementation.
        """
        system = platform.system()
        
        try:
            import subprocess
            
            if system == "Darwin":  # macOS
                result = subprocess.run(
                    ["pbpaste"], capture_output=True, text=True, timeout=3
                )
                return result.stdout.strip() if result.returncode == 0 else ""
            
            elif system == "Linux":
                # Try wl-copy (Wayland), then xclip, then xsel
                for cmd in [
                    ["wl-paste", "--type", "text/plain"],
                    ["xclip", "-selection", "clipboard", "-o"],
                    ["xsel", "--clipboard", "--output"],
                ]:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                    if result.returncode == 0 and result.stdout.strip():
                        return result.stdout.strip()
                return ""
            
            elif system == "Windows":
                import ctypes
                
                CF_UNICODETEXT = 13
                GMEM_MOVEABLE = 0x0002
                
                ctypes.windll.user32.OpenClipboard(0)
                handle = ctypes.windll.user32.GetClipboardData(CF_UNICODETEXT)
                
                if handle:
                    data = ctypes.c_char_p(ctypes.windll.kernel32.LockGMEM(handle))
                    text = data.value.decode("utf-16-le", errors="ignore")
                    ctypes.windll.kernel32.UnlockGMEM(handle)
                    ctypes.windll.user32.CloseClipboard()
                    return text.strip()
                else:
                    ctypes.windll.user32.CloseClipboard()
                    return ""
            
        except Exception as e:
            logger.debug(f"Clipboard read failed on {system}: {e}")
        
        return ""

    def _detect_type(self, text: str) -> ContentType:
        """Heuristic content type detection from text."""
        lower = text.lower()
        
        # Code detection
        code_indicators = ["def ", "function ", "class ", "const ", "let ",
                          "import ", "from ", "=>", "{", "};", "#!/"]
        if sum(1 for i in code_indicators if i in text) >= 2:
            return ContentType.CODE
        
        # URL / bookmark
        if text.startswith("http://") or text.startswith("https://") or text.startswith("www."):
            if len(text) < 500:
                return ContentType.BOOKMARK
        
        # Academic paper indicators
        paper_words = ["abstract", "introduction", "methodology", "conclusion",
                       "references", "doi:", "arxiv", "journal of"]
        if sum(1 for w in paper_words if w in lower) >= 2:
            return ContentType.PAPER
        
        # Article / long-form
        if len(text) > 1000:
            return ContentType.ARTICLE
        
        # Note / short-form
        return ContentType.NOTE

    def _extract_title(self, text: str) -> str:
        """Extract a title from the beginning of text."""
        lines = text.lstrip().split("\n")
        
        # First non-empty line is usually title
        for line in lines[:5]:
            line = line.strip()
            # Skip markdown formatting chars
            line_clean = line.lstrip("#*-> ")
            if line_clean and len(line_clean) < 200:
                return line_clean
        
        # Fallback: first ~50 chars
        first_line = lines[0].lstrip("#*-> ") if lines else ""
        return first_line[:50] if first_line else f"Clipboard Note"
