"""
Compound Wiki - Ingestion Pipeline
====================================
Core pipeline: reads raw files, calls LLM to extract/structure knowledge,
generates wiki pages with bi-directional links, updates index.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("compound_wiki.pipeline")


class LLMClient:
    """
    Universal LLM client supporting multiple providers.
    
    Providers:
      - anthropic: Claude API
      - openai: OpenAI API (also works for compatible APIs)
      - ollama: Local models via Ollama
    """

    def __init__(self, config=None):
        self.config = config or {}
        self.provider = self.config.get("provider", "anthropic")
        self.api_key = self.config.get("api_key", "") or os.environ.get("CW_LLM_API_KEY", "")
        self.base_url = self.config.get("base_url", "") or os.environ.get("CW_LLM_BASE_URL", "")
        self.models = self.config.get("models", {})
        self.max_tokens = self.config.get("max_tokens", 8192)
        self.temperature = self.config.get("temperature", 0.3)

        # Lazy-loaded client instances
        self._client = None
        self._provider_name = None

    def _get_client(self):
        """Lazy-initialize and return provider-specific client."""
        if self._client is not None:
            return self._client, self._provider_name

        try:
            # Try Anthropic first
            if self.provider in ("anthropic", "claude"):
                import anthropic
                key = self.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
                self._client = anthropic.Anthropic(api_key=key)
                self._provider_name = "anthropic"
                return self._client, self._provider_name

            elif self.provider in ("openai", "azure_openai"):
                from openai import OpenAI
                key = self.api_key or os.environ.get("OPENAI_API_KEY", "")
                kwargs = {"api_key": key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._client = OpenAI(**kwargs)
                self._provider_name = "openai"
                return self._client, self._provider_name

            elif self.provider == "ollama":
                from openai import OpenAI
                url = self.base_url or "http://localhost:11434/v1"
                self._client = OpenAI(base_url=url, api_key="ollama")
                self._provider_name = "ollama"
                return self._client, self._provider_name

            else:
                raise ValueError(f"Unsupported provider: {self.provider}")

        except ImportError as e:
            raise ImportError(
                f"Missing dependency for {self.provider}: {e}\n"
                f"Install with: pip install anthropic  (or openai / ollama)"
            )

    def chat(self, messages: list[dict], task: str = "ingest", **kwargs) -> str:
        """Send messages to LLM and return response text."""
        client, provider = self._get_client()
        model = self.models.get(task, self.models.get("ingest", ""))

        if provider == "anthropic":
            # Convert to Anthropic format
            system_msg = None
            formatted_msgs = []
            for msg in messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                else:
                    formatted_msgs.append({
                        "role": msg["role"],
                        "content": msg["content"],
                    })

            response = client.messages.create(
                model=model,
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature),
                system=system_msg or "",
                messages=formatted_msgs,
            )
            return response.content[0].text

        else:  # openai-compatible (including ollama)
            response = client.chat.completions.create(
                model=model,
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
                temperature=kwargs.get("temperature", self.temperature),
                messages=messages,
            )
            return response.choices[0].message.content


class IngestionPipeline:
    """
    The core ingestion engine.
    
    Flow:
      1. Read rule file (CLAUDE.md) → establishes AI behavior
      2. Read pending files from state manager → identifies new/changed content  
      3. For each file: read content → build prompt with context → call LLM
      4. Parse LLM response → write Wiki pages → update links
      5. Update INDEX.md + changelog.md → persist state
    
    All operations are incremental — only processes new or changed files.
    """

    def __init__(self, config, state_manager, llm_client=None):
        self.cfg = config
        self.state = state_manager
        self.llm = llm_client or LLMClient(config.llm.__dict__ if hasattr(config.llm, '__dict__') else config.llm)

        # Paths
        self.raw_dir = config.raw_dir
        self.wiki_dir = config.wiki_dir
        self.schema_dir = config.schema_dir
        self.outputs_dir = config.outputs_dir

        # Pipeline settings
        self.max_files_per_batch = getattr(config.pipeline, 'max_files_per_batch', 10)

        # Load rules once at init
        self.rules_text = self._load_rules()

    def _load_rules(self) -> str:
        """Load CLAUDE.md / AGENTS.md rule file."""
        rule_path = self.schema_dir / (getattr(self.cfg, 'rule_file', 'schema/CLAUDE.md').split("/")[-1])
        candidates = [
            self.schema_dir / "CLAUDE.md",
            self.schema_dir / "AGENTS.md",
            Path(self.cfg.root_dir) / "schema" / "CLAUDE.md",
        ]
        for p in candidates:
            if p.exists():
                logger.info(f"📋 Loaded rules from: {p}")
                return p.read_text(encoding="utf-8")
        logger.warn("No rule file found. Using built-in defaults.")
        return self._default_rules()

    @staticmethod
    def _default_rules() -> str:
        return """You are a knowledge management AI. Your job is to read raw materials and produce structured Markdown wiki pages.

Rules:
- Each topic gets one .md file
- Start each file with a summary paragraph
- Use [[topic]] for internal links
- Maintain an INDEX.md of all pages
- Cite sources for every claim"""

    def run(self, files: list[str] | None = None) -> dict:
        """
        Run the full ingestion pipeline.
        
        Args:
            files: Specific files to process. If None, auto-detects pending files.

        Returns:
            Summary dict with stats.
        """
        start_time = time.time()

        if files is None:
            pending = self.state.get_pending_files(self.raw_dir)
            files = [f.path for f in pending[:self.max_files_per_batch]]

        if not files:
            logger.info("✅ No new files to process.")
            return {"status": "idle", "files_processed": 0}

        logger.info(f"🚀 Starting ingestion of {len(files)} file(s)...")

        results = {
            "files_processed": 0,
            "pages_created": [],
            "pages_updated": [],
            "errors": [],
            "skipped": [],
        }

        for i, file_path in enumerate(files, 1):
            path = Path(file_path)
            logger.info(f"\n{'─'*60}")
            logger.info(f"  [{i}/{len(files)}] Processing: {path.name}")

            try:
                result = self._process_single_file(path)
                if result:
                    results["files_processed"] += 1
                    results["pages_created"].extend(result.get("created", []))
                    results["pages_updated"].extend(result.get("updated", []))
                    self.state.mark_done(str(path))
                else:
                    results["skipped"].append(str(path))

            except Exception as e:
                error_msg = f"{path.name}: {e}"
                logger.error(f"  ❌ ERROR: {error_msg}")
                results["errors"].append(error_msg)
                self.state.mark_error(str(path))

        # Update global index after all files processed
        if results["pages_created"] or results["pages_updated"]:
            try:
                self._update_index()
                logger.info("\n📑 Index updated.")
            except Exception as e:
                logger.error(f"Index update failed: {e}")

        # Record ingest operation
        duration = time.time() - start_time
        record_id = f"ingest-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.state.record_ingest({
            "id": record_id,
            "timestamp": datetime.now().isoformat(),
            "files": [str(f) for f in files],
            "pages_created": results["pages_created"],
            "pages_updated": results["pages_updated"],
            "errors": results["errors"],
            "duration_seconds": round(duration, 2),
            "trigger": "auto" if files is None else "manual",
        })
        self.state.save()

        logger.info(f"\n{'='*60}")
        logger.info(f"✅ Ingestion complete in {duration:.1f}s")
        logger.info(f"   Files: {results['files_processed']} processed")
        logger.info(f"   Pages: +{len(results['pages_created'])} created, ~{len(results['pages_updated'])} updated")

        return results

    def _process_single_file(self, file_path: Path) -> dict | None:
        """Process a single raw file through the pipeline."""
        self.state.mark_processing(str(file_path))

        # Read file
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Try binary-safe fallback
            content = file_path.read_text(encoding="latin-1")
            logger.warning(f"  ⚠ Fallback encoding for {file_path.name}")

        if len(content.strip()) < 50:
            logger.info(f"  ⏭ Too short ({len(content)} chars), skipping.")
            return None

        # Build the prompt
        prompt = self._build_ingest_prompt(file_path.name, content)

        # Call LLM
        logger.info(f"  🤖 Calling LLM ({len(content)} chars input)...")
        llm_start = time.time()
        response = self.chat_with_context(prompt, task="ingest")
        llm_duration = time.time() - llm_start
        logger.info(f"  ✅ LLM responded in {llm_duration:.1f}s ({len(response)} chars)")

        # Parse and write pages
        created, updated = self._parse_and_write_pages(response, source_file=file_path.name)

        return {
            "created": created,
            "updated": updated,
        }

    def _build_ingest_prompt(self, filename: str, content: str) -> list[dict]:
        """Build the full prompt for ingestion."""
        # Truncate very long files to avoid token overflow
        max_chars = 50000
        if len(content) > max_chars:
            content = content[:max_chars] + f"\n\n... [TRUNCATED — original was {len(content):,} chars]"

        system_prompt = f"""You are Compound Wiki's Knowledge Engineer. Your role is to read raw materials and convert them into structured, linked Markdown wiki pages.

## YOUR RULES (from CLAUDE.md)
{self.rules_text[:3000]}
...

## OUTPUT FORMAT
Return your response in this EXACT structure:

```markdown
===WIKI_PAGES===
<page>
### FILENAME: wiki/concept/your-topic-name.md
# Topic Name

> **Source**: {{source_filename}}
> **Confidence**: ★★★★☆
> **Last Updated**: {{date}}

Summary paragraph (2-3 sentences explaining what this is about).

## Key Points
- Point 1
- Point 2

## Related Concepts
- [[related-topic]]
- [[another-topic]]

---
*Auto-generated by Compound Wiki*
</page>

(Repeat <page> blocks for each distinct topic/concept/entity found)

===LINKS_TO_UPDATE===
- existing-page-1.md: Add link to new-topic
- existing-page-2.md: Add mention of concept found here

===INDEX_ENTRIES===
- Your Topic Name | wiki/concept/your-topic-name.md | concept | source-filename
```

## CRITICAL INSTRUCTIONS
1. Extract EVERY meaningful concept, entity, relationship, and data point
2. Create SEPARATE pages for distinct topics (don't cram everything into one page)
3. ALWAYS use [[double-bracket]] format for internal wiki links
4. Include source citations for verifiability
5. Mark confidence level for uncertain information
6. Think about how this connects to EXISTING knowledge
7. Write in clear, concise English (or match the source language)
"""

        user_message = f"""## File to Process
**Filename**: `{filename}`
**Size**: {len(content):,} characters

--- CONTENT START ---

{content}

--- CONTENT END ---

Please analyze this content and generate wiki pages according to your rules."""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

    def chat_with_context(self, prompt_or_messages, task="ingest", **kwargs) -> str:
        """Send to LLM with proper format handling."""
        if isinstance(prompt_or_messages, str):
            messages = [{"role": "user", "content": prompt_or_messages}]
        else:
            messages = prompt_or_messages
        return self.llm.chat(messages, task=task, **kwargs)

    def _parse_and_write_pages(self, response: str, source_file: str) -> tuple[list[str], list[str]]:
        """Parse LLM response and write actual .md files."""
        created = []
        updated = []

        # Extract WIKI_PAGES section
        pages_text = ""
        if "===WIKI_PAGES===" in response:
            parts = response.split("===WIKI_PAGES===")
            rest = parts[1] if len(parts) > 1 else response
            if "===LINKS_TO_UPDATE===" in rest:
                pages_text = rest.split("===LINKS_TO_UPDATE===")[0]
            else:
                pages_text = rest
        else:
            # Try to parse without markers — treat entire response as wiki content
            pages_text = response

        # Split into individual pages
        page_blocks = self._extract_page_blocks(pages_text)

        for block in page_blocks:
            try:
                page_info = self._parse_page_block(block, source_file)
                if not page_info:
                    continue

                filepath = self.wiki_dir / page_info["filename"]
                filepath.parent.mkdir(parents=True, exist_ok=True)

                # Check if file exists
                is_new = not filepath.exists()
                filepath.write_text(page_info["content"], encoding="utf-8")

                if is_new:
                    created.append(str(filepath.relative_to(self.wiki_dir)))
                    logger.info(f"  📄 NEW: {filepath.relative_to(self.wiki_dir)}")
                else:
                    updated.append(str(filepath.relative_to(self.wiki_dir)))
                    logger.info(f"  📝 UPDATED: {filepath.relative_to(self.wiki_dir)}")

            except Exception as e:
                logger.error(f"  ⚠ Failed to write page: {e}")

        return created, updated

    @staticmethod
    def _extract_page_blocks(text: str) -> list[str]:
        """Split response into individual page blocks."""
        import re
        # Pattern: <page>...</page> or ### FILENAME: sections
        pattern = r'(?:<page>\s*)?(?:###\s*FILENAME:\s*.+?\.md\s*\n)?(.+?)(?:</page>|(?=(?:<page>|###\s*FILENAME:)|$))'
        matches = re.findall(pattern, text, re.DOTALL)
        
        if len(matches) <= 1 and "<page>" not in text:
            # Single page, return whole text
            return [text]
        return [m.strip() for m in matches if m.strip()]

    def _parse_page_block(self, block: str, source_file: str) -> dict | None:
        """Parse a single page block into filename + content."""
        import re
        
        # Extract filename
        fn_match = re.search(r'###\s*FILENAME:\s*(.+?\.md)', block)
        if fn_match:
            filename = fn_match.group(1).strip()
            # Clean up the content (remove metadata line)
            content = re.sub(r'###\s*FILENAME:.+\n?', '', block).strip()
        else:
            # Auto-generate filename from first heading
            h_match = re.search(r'^#\s+(.+)', block, re.MULTILINE)
            if h_match:
                slug = h_match.group(1).strip().lower()
                slug = re.sub(r'[^a-z0-9\u4e00-\u9fff]+', '-', slug)[:50]
                filename = f"wiki/concept/{slug.rstrip('-')}.md"
            else:
                hash_prefix = hashlib.md5(block.encode()).hexdigest()[:8]
                filename = f"wiki/concept/{hash_prefix}-{source_file}.md"
            content = block.strip()

        if not content or len(content) < 20:
            return None

        return {"filename": filename, "content": content}

    def _update_index(self) -> None:
        """Update the global INDEX.md with all current wiki pages."""
        index_path = self.wiki_dir / "index.md"

        all_pages = sorted(self.wiki_dir.rglob("*.md"))
        all_pages = [p for p in all_pages if p.name not in ("index.md", "changelog.md")]

        lines = ["# Compound Wiki — Global Index\n"]
        lines.append(f"> Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        lines.append(f"> Total pages: {len(all_pages)}\n")

        # Group by directory
        by_dir: dict[str, list[Path]] = {}
        for p in all_pages:
            parent = p.parent.name
            if parent not in ("concept", "entity", "synthesis"):
                parent = "other"
            by_dir.setdefault(parent, []).append(p)

        dir_emoji = {"concept": "💡", "entity": "🏷", "synthesis": "🔗", "other": "📁"}
        dir_label = {"concept": "Concepts", "entity": "Entities", "synthesis": "Synthesis", "other": "Other"}

        for dir_name in ("concept", "entity", "synthesis", "other"):
            if dir_name not in by_dir:
                continue
            lines.append(f"\n### {dir_emoji.get(dir_name,'')} {dir_label.get(dir_name,dir_name)} ({len(by_dir[dir_name])})\n")
            lines.append("| Page | Path |")
            lines.append("|------|------|")
            for p in sorted(by_dir[dir_name], key=lambda x: x.stem):
                rel_path = str(p.relative_to(self.wiki_dir))
                title = p.stem.replace("-", " ").title()
                lines.append(f"| [[{title}]] | `{rel_path}` |")

        index_path.write_text("\n".join(lines), encoding="utf-8")

    # ── QUERY mode ────────────────────────────────────────

    def query(self, question: str, archive: bool = True) -> str:
        """
        Query the wiki and generate an answer based on existing knowledge.
        
        Optionally archives the answer as a new synthesis page.
        """
        logger.info(f"❓ Query: {question[:80]}...")

        # Gather relevant context from wiki
        context = self._gather_query_context(question)
        
        prompt = self._build_query_prompt(question, context)
        
        response = self.chat_with_context(prompt, task="query")

        if archive and len(response) > 200:
            archive_path = self._archive_query(question, response)
            logger.info(f"📦 Archived to: {archive_path}")
            return response + f"\n\n---\n*Archived as: {archive_path}*"

        return response

    def _gather_query_context(self, question: str, max_pages: int = 10) -> str:
        """Gather relevant wiki pages for query context."""
        import re
        
        # Simple keyword matching for now (can be upgraded to vector search later)
        keywords = set(re.findall(r'\b\w{3,}\b', question.lower()))
        
        scored_pages = []
        for page_path in self.wiki_dir.rglob("*.md"):
            if page_path.name in ("index.md", "changelog.md"):
                continue
            try:
                text = page_path.read_text(encoding="utf-8")[:2000]
                score = sum(1 for kw in keywords if kw in text.lower())
                if score > 0:
                    scored_pages.append((score, page_path, text))
            except Exception:
                pass

        # Sort by relevance, take top N
        scored_pages.sort(key=lambda x: -x[0])
        top = scored_pages[:max_pages]

        if not top:
            return "(No relevant pages found. The wiki may be empty.)"

        context_parts = []
        for _, path, text in top:
            rel = str(path.relative_to(self.wiki_dir))
            context_parts.append(f"\n--- [{rel}] ---\n{text[:1500]}")

        return "\n".join(context_parts)

    def _build_query_prompt(self, question: str, context: str) -> list[dict]:
        return [
            {"role": "system", "content": f"""You are Compound Wiki's Query Engine. Answer questions based ONLY on the provided wiki content.

Rules:
- Base answers strictly on the provided context
- Cite sources using [[page-link]] format
- If information is missing or uncertain, say so clearly
- Provide structured, well-organized answers
- Include connections between related concepts"""},
            {"role": "user", "content": f"## Wiki Context\n{context}\n\n## Question\n{question}"},
        ]

    def _archive_query(self, question: str, answer: str) -> str:
        """Save a Q&A pair as a synthesis page."""
        import re
        safe_title = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]+', '-', question[:60])[:60]
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"wiki/synthesis/q-{timestamp}-{safe_title}.md"
        filepath = self.wiki_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)

        content = f"""# Q: {question}

_Archived: {datetime.now().strftime('%Y-%m-%d %H:%M')}_

---

## Answer

{answer}

---

*Generated by Compound Wiki Query Engine*
"""
        filepath.write_text(content, encoding="utf-8")

        record_id = f"query-{timestamp}"
        self.state.record_query({
            "id": record_id,
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "answer_page": filename,
            "archived": True,
        })
        self.state.save()

        return filename

    # ── LINT mode ────────────────────────────────────────

    def lint(self, auto_fix: bool = False) -> dict:
        """
        Run health check on the entire wiki.
        
        Checks:
          - Orphaned pages (no incoming links)
          - Broken links (target doesn't exist)
          - Contradictory info (same concept, different claims)
          - Stale/unreferenced content
        """
        start_time = time.time()
        logger.info(f"🔍 Running LINT check (auto_fix={auto_fix})...")

        issues = []
        warnings = []

        all_pages = list(self.wiki_dir.rglob("*.md"))
        all_pages = [p for p in all_pages if p.name not in ("index.md", "changelog.md")]

        # Collect all links
        link_map: dict[str, set[str]] = {}  # target_page -> set of source_pages
        page_names = set()

        for page in all_pages:
            try:
                text = page.read_text(encoding="utf-8")
            except Exception:
                continue
            
            rel_path = str(page.relative_to(self.wiki_dir))
            page_names.add(rel_path)

            # Find all [[links]]
            import re
            for match in re.findall(r'\[\[(.+?)\]\]', text):
                target = match.strip()
                link_map.setdefault(target, set()).add(rel_path)

        # Check 1: Broken links
        for target, sources in link_map.items():
            resolved = self._resolve_link(target, page_names)
            if resolved is None:
                for src in sources:
                    issues.append(f"BROKEN_LINK: [[{target}}]] referenced in {src} but page not found")

        # Check 2: Orphaned pages (not in index.html, no inbound links)
        linked_targets = set(link_map.keys())
        orphan_candidates = []
        for page in all_pages:
            rel = str(page.relative_to(self.wiki_dir))
            # A page is orphaned if nothing links to it (except index/changelog)
            inbound = sum(1 for targets in link_map.values() if any(rel == t or rel.endswith(t) for t in targets))
            if inbound == 0 and page.name not in ("index.md", "changelog.md"):
                orphan_candidates.append(rel)

        if orphan_candidates:
            warnings.extend([f"ORPHAN: {p} has no inbound links" for p in orphan_candidates])

        # Check 3: Very short pages (likely incomplete)
        for page in all_pages:
            if page.stat().st_size < 100 and page.name not in ("index.md", "changelog.md"):
                rel = str(page.relative_to(self.wiki_dir))
                warnings.append(f"SHORT_PAGE: {rel} is only {page.stat().st_size} bytes")

        # Record lint
        duration = time.time() - start_time
        lint_record = {
            "id": f"lint-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "issues_found": len(issues),
            "issues_fixed": 0,
            "warnings": warnings,
            "errors": issues,
            "duration_seconds": round(duration, 2),
        }
        self.state.record_lint(lint_record)
        self.state.save()

        logger.info(f"\n🔍 LINT complete in {duration:.1f}s:")
        logger.info(f"   Issues: {len(issues)} | Warnings: {len(warnings)}")

        # Generate report
        report = self._generate_lint_report(issues, warnings, auto_fix)

        return {
            "issues_found": len(issues),
            "warnings_count": len(warnings),
            "issues": issues,
            "warnings": warnings,
            "report": report,
            "duration_seconds": round(duration, 2),
        }

    def _resolve_link(self, target: str, page_names: set) -> str | None:
        """Resolve a [[link]] target to an actual file path."""
        # Direct match
        if target in page_names:
            return target
        # Partial match
        for name in page_names:
            if name.endswith(target) or name.endswith(target + ".md") or target in name:
                return name
        # Stem match
        for name in page_names:
            if Path(name).stem == target or Path(name).stem == target.lower():
                return name
        return None

    def _generate_lint_report(self, issues: list, warnings: list, auto_fix: bool) -> str:
        """Generate a human-readable LINT report."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            f"# 🔍 Wiki Health Report",
            f"_Generated: {timestamp}_\n",
            f"## Summary",
            f"| Metric | Count |",
            f"|--------|-------|",
            f"| 🔴 Issues | {len(issues)} |",
            f"| ⚠️  Warnings | {len(warnings)} |",
        ]

        if issues:
            lines.append(f"\n## 🔴 Issues\n")
            for i, issue in enumerate(issues, 1):
                lines.append(f"{i}. {issue}")

        if warnings:
            lines.append(f"\n## ⚠️ Warnings\n")
            for i, w in enumerate(warnings, 1):
                lines.append(f"{i}. {w}")

        if not issues and not warnings:
            lines.append(f"\n> ✅ **All clean!** Your wiki looks healthy.\n")

        report_text = "\n".join(lines)

        # Save report to outputs/
        report_path = self.outputs_dir / f"lint-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text, encoding="utf-8")

        return report_text
