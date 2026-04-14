"""
Email Source Plugin
===================

Watch an IMAP email inbox and ingest new emails into the Wiki.

Useful for:
  • Newsletter subscriptions (auto-ingest articles)
  • Research paper alerts (arXiv, Google Scholar)
  • Important email threads you want in your knowledge base
  • Meeting notes sent via email

Configuration (settings):
    imap_host: "imap.gmail.com"
    imap_port: 993
    username: "your@email.com"
    password: "app-specific-password"  # Use app password, not real one!
    folder: "INBOX"                   # or specific label/folder
    mark_as_seen: false                # keep unread after processing
    filters:
      only_from: []                    # only process from these senders
      subject_contains: []             # only if subject contains these
      skip_no_reply: true              # skip noreply@ addresses

Usage:
    source = EmailSource(SourceConfig(
        settings={
            "imap_host": "imap.gmail.com",
            "username": "...",
            "password": "app-password",
            "filters": {"subject_contains": ["newsletter", "paper"]}
        }
    ))
    await source.start()
"""

import asyncio
import email
import logging
from datetime import datetime
from email import policy
from email.parser import BytesParser
from typing import Any, Dict, List, Optional

from .base import BaseSource, IngestItem, SourceConfig, SourceType, ContentType

logger = logging.getLogger("cw-source-email")


class EmailSource(BaseSource):
    """IMAP email watcher for automatic ingestion."""

    @property
    def source_type(self) -> SourceType:
        return SourceType.EMAIL

    @property
    def display_name(self) -> str:
        return "Email Watcher"

    @property
    def description(self) -> str:
        return "Watch IMAP inbox for new emails to auto-ingest"

    async def start(self):
        await super().start()
        
        self._queue: List[IngestItem] = []
        self._seen_uids: set = set()
        self._poll_interval = self.config.settings.get("poll_interval", 60)
        self._folder = self.config.settings.get("folder", "INBOX")
        
        logger.info(f"📧 Email watcher started (folder={self._folder}, interval={self._poll_interval}s)")
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
                await self._check_mailbox()
            except Exception as e:
                logger.warning(f"Email poll error: {e}")
            await asyncio.sleep(self._poll_interval)

    async def _check_mailbox(self):
        """Check IMAP mailbox for new messages."""
        try:
            import aioimaplib
            
            host = self.config.settings["imap_host"]
            port = int(self.config.settings.get("imap_port", 993))
            user = self.config.settings["username"]
            pwd = self.config.settings["password"]
            
            client = aioimaplib.IMAP4_SSL(host=host, port=port)
            await client.wait_hello_from_server()
            await client.login(user, pwd)
            await client.select(self._folder)
            
            # Search for recent unseen messages
            status, data = await client.search('UNSEEN')
            if status == 'OK' and data[0]:
                uids = data[0].split()
                
                for uid in uids:
                    uid_str = uid.decode() if isinstance(uid, bytes) else str(uid)
                    if uid_str in self._seen_uids:
                        continue
                    
                    # Fetch message
                    status, msg_data = await client.fetch(uid_str, '(BODY.PEEK[])')
                    if status != 'OK' or not msg_data or not msg_data[0]:
                        continue
                    
                    raw_bytes = msg_data[0][1] if isinstance(msg_data[0], tuple) else msg_data[0]
                    msg = email.message_from_bytes(raw_bytes, policy=policy.default)
                    
                    item = self._parse_email(msg, uid_str)
                    if item and self.validate_item(item):
                        self._queue.append(item)
                        self._seen_uids.add(uid_str)
                        logger.info(f"📧 Ingested email: {item.title}")
                    
                    # Mark as seen if configured
                    if not self.config.settings.get("mark_as_seen", False):
                        await client.store(uid_str, '+FLAGS', '\\Seen')
            
            await client.logout()
            
        except ImportError:
            logger.warning("aioimaplib not installed — pip install aioimaplib")
        except Exception as e:
            logger.error(f"IMAP error: {e}")

    def _parse_email(self, msg, uid: str) -> Optional[IngestItem]:
        """Parse email message into IngestItem."""
        filters = self.config.filters
        
        # Sender filter
        sender = msg.get("From", "")
        if filters.get("skip_no_reply") and "noreply" in sender.lower():
            return None
        if filters.get("only_from"):
            if not any(s.lower() in sender.lower() for s in filters["only_from"]):
                return None
        
        # Subject filter  
        subject = msg.get("Subject", "(No Subject)")
        if filters.get("subject_contains"):
            if not any(kw.lower() in subject.lower() for kw in filters["subject_contains"]):
                return None
        
        # Extract body text
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ct = part.get_content_type()
                if ct == "text/plain":
                    payload = part.get_payload(decode=True)
                    body = (payload or b"").decode(errors="replace")
                    break
                elif ct == "text/html" and not body:
                    # Strip HTML as fallback
                    payload = part.get_payload(decode=True)
                    raw_html = (payload or b"").decode(errors="replace")
                    body = _strip_html(raw_html)
        else:
            payload = msg.get_payload(decode=True)
            body = (payload or b"").decode(errors="replace")
        
        if len(body.strip()) < 20:
            return None
        
        return IngestItem(
            content=body,
            title=subject,
            source_type=SourceType.EMAIL,
            content_type=self._detect_email_type(subject, body),
            metadata={
                "uid": uid,
                "from": sender,
                "to": msg.get("To", ""),
                "date": msg.get("Date", ""),
                "message_id": msg.get("Message-ID", ""),
            },
            tags=["email"],
        )

    @staticmethod
    def _detect_email_type(subject: str, body: str) -> ContentType:
        lower = (subject + " " + body).lower()
        if any(w in lower for w in ["newsletter", "weekly", "digest", "substack"]):
            return ContentType.ARTICLE
        if any(w in lower for w in ["arxiv", "research paper", "publication"]):
            return ContentType.PAPER
        return ContentType.ARTICLE


def _strip_html(html: str) -> str:
    """Simple HTML tag stripper."""
    import re
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.S)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.S)
    html = re.sub(r'<[^>]+>', ' ', html)
    html = re.sub(r'\s+', ' ', html).strip()
    return html
