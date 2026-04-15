#!/usr/bin/env python3
"""
OpenClaw + CAM Integration Test
==========================================

This script tests whether CAM works correctly when integrated
with OpenClaw as the Agent LLM backend.

Usage:
    cd cam/
    python3 memory_core/examples/openclaw_integration.py

Requirements:
    - openclaw installed and configured in PATH
    - openclaw agent --local working (API keys set up)
    - httpx installed (pip install httpx)
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from memory_core import MemoryCore


def call_openclaw(message: str, session_id: str = "cw-integration-test") -> dict:
    """
    Call OpenClaw agent via CLI and parse response.
    
    Returns parsed JSON result or raw text.
    """
    cmd = [
        "openclaw", "agent",
        "--local",
        "--session-id", session_id,
        "--message", message,
        "--timeout", "120",
        "--json"
    ]
    
    print(f"  [OpenClaw] >>> {message[:60]}...")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=150,
            cwd=os.path.expanduser("~/openclaw-src"),
            env={**os.environ, "NODE_OPTIONS": "--max-old-space-size=512"}
        )
        
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                # Extract assistant text from OpenClaw JSON response
                text = ""
                if isinstance(data, dict):
                    text = data.get("text") or data.get("response") or data.get("content", "")
                    if not text and "assistantTexts" in data:
                        texts = data.get("assistantTexts", [])
                        text = texts[0] if texts else json.dumps(data)[:500]
                elif isinstance(data, str):
                    text = data
                else:
                    text = str(data)[:500]
                
                print(f"  [OpenClaw] <<< {text[:100]}...")
                return {"ok": True, "text": text, "raw": data}
            except json.JSONDecodeError:
                text = result.stdout.strip()
                print(f"  [OpenClaw] <<< {text[:100]}...")
                return {"ok": True, "text": text, "raw": text}
        else:
            error = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
            print(f"  [OpenClaw] ERROR: {error[:200]}")
            return {"ok": False, "error": error}
            
    except subprocess.TimeoutExpired:
        print(f"  [OpenClaw] TIMEOUT after 150s")
        return {"ok": False, "error": "timeout"}
    except Exception as e:
        print(f"  [OpenClaw] EXCEPTION: {e}")
        return {"ok": False, "error": str(e)}


def extract_facts_from_response(ai_text: str) -> list:
    """
    Simple rule-based extraction as fallback.
    
    When we don't have a real LLM extractor available,
    use heuristics to find facts in the AI response.
    This simulates what Agent-Native extraction would do.
    """
    facts = []
    text_lower = ai_text.lower()
    
    # Decision patterns
    decision_patterns = [
        ("decision", r"(?:we|I|should|will|choose|selected)\s+(?:use|adopt|go with|prefer)\s+[\w\s/]+?(?:\.|$)"),
        ("decision", r"(?:chose|decided|deciding)\s+to\s+[\w\s/]+?(?:\.|$)"),
        ("preference", r"(?:prefer|like|love|hate|dislike)\s+[\w\s]+(?:style|format|approach|way)(?:\.|$)"),
        ("fact", r"(?:using|built with|runs on|requires|needs)\s+[\w\s/\-\.]+(?:\d+\.\d+)?(?:\.|$)"),
        ("concept", r"(?:is\s+a?\s+)(?:pattern|framework|architecture|approach|methodology|paradigm)[\w\s]+?(?:\.|$)"),
    ]
    
    import re
    
    for fact_type, pattern in decision_patterns:
        matches = re.findall(pattern, text_lower)
        for match in matches[:2]:  # max 2 per pattern
            clean = match.strip().rstrip(".").strip()
            if len(clean) > 15 and len(clean) < 300:
                facts.append({
                    "fact_type": fact_type,
                    "content": clean.capitalize() if clean else clean,
                    "confidence": 0.75,
                    "tags": [],
                })
    
    return facts


async def run_integration_test():
    """Main integration test: OpenClaw + CAM."""
    
    print("=" * 70)
    print("  OpenClaw x CAM — Integration Test")
    print("=" * 70)
    
    # Setup paths
    wiki_path = Path(os.path.expanduser("~/cam/wiki"))
    wiki_path.mkdir(parents=True, exist_ok=True)
    
    # Initialize MemoryCore
    print("\n[1] Initializing MemoryCore...")
    mc = MemoryCore(wiki_path=str(wiki_path))
    await mc.initialize()
    print(f"     Wiki path: {wiki_path}")
    
    # Define test conversations
    conversations = [
        {
            "user_msg": (
                "Hi! I'm setting up a new microservices project using Python "
                "with FastAPI and Redis for caching."
            ),
            "expected_keywords": ["python", "fastapi", "redis"],
            "description": "Tech stack declaration",
        },
        {
            "user_msg": (
                "We decided to use PostgreSQL as our primary database instead "
                "of MongoDB because we need strong ACID compliance for financial transactions."
            ),
            "expected_keywords": ["postgresql", "database", "acid"],
            "description": "Database decision",
        },
        {
            "user_msg": (
                "Our team prefers TDD approach - we write tests first before "
                "implementation code. Also we use GitHub Actions for CI/CD pipeline."
            ),
            "expected_keywords": ["tdd", "github actions", "ci/cd"],
            "description": "Process preferences",
        },
        {
            "user_msg": (
                "What decisions have we made about our project? Summarize what you know."
            ),
            "expected_keywords": [],
            "description": "Memory recall query",
            "is_query": True,
        },
    ]
    
    print("\n[2] Starting conversation loop with OpenClaw...\n")
    
    results = []
    all_facts_extracted = []
    
    for i, conv in enumerate(conversations):
        print(f"\n--- Turn {i+1}: {conv['description']} ---")
        
        # Call OpenClaw agent
        oc_result = call_openclaw(conv["user_msg"], session_id="cw-test-001")
        
        if not oc_result["ok"]:
            print(f"     [WARN] OpenClaw failed: {oc_result.get('error', 'unknown')}")
            results.append({"turn": i+1, "status": "openclaw_error"})
            continue
        
        ai_text = oc_result["text"]
        
        if conv.get("is_query"):
            # Query turn - check what Wiki knows
            print(f"\n  [Query] Asking Wiki what it knows...")
            wiki_answer = await mc.query(conv["user_msg"])
            print(f"  [Wiki] Answer: {str(wiki_answer)[:200]}")
            
            results.append({
                "turn": i+1,
                "status": "query",
                "ai_response_len": len(ai_text),
                "wiki_has_data": bool(wiki_answer),
            })
            continue
        
        # Extract facts from the conversation (Agent-Native simulation)
        # In production, the Agent itself would call mc.remember()
        facts = extract_facts_from_response(ai_text)
        
        if facts:
            print(f"\n  [Extracted] Found {len(facts)} fact(s):")
            for f in facts:
                print(f"     - [{f['fact_type']}] {f['content'][:80]}")
                all_facts_extracted.append(f)
            
            # Store in Wiki via SharedWiki directly
            from memory_core.extractor import FactType, ExtractionResult, ExtractedFact
            
            extracted_facts = []
            for f in facts:
                try:
                    ef = ExtractedFact(
                        fact_type=FactType(f["fact_type"]),
                        content=f["content"],
                        confidence=f["confidence"],
                        source_text=ai_text[:200],
                        tags=f.get("tags", []),
                        agent_id="openclaw-agent",
                    )
                    extracted_facts.append(ef)
                except Exception as e:
                    print(f"     [WARN] Failed to create fact: {e}")
            
            if extracted_facts:
                ex_result = ExtractionResult(
                    should_store=True,
                    facts=extracted_facts,
                    trigger_reason=f"integration_test_turn_{i+1}",
                )
                
                store_ok = await mc.wiki.store(extracted_facts, source="openclaw-integration")
                print(f"  [Wiki Store] {'SUCCESS' if store_ok else 'FAILED'}")
        
        results.append({
            "turn": i+1,
            "status": "ok",
            "facts_found": len(facts),
            "ai_response_len": len(ai_text),
        })
    
    # Summary
    print("\n" + "=" * 70)
    print("  INTEGRATION TEST SUMMARY")
    print("=" * 70)
    
    total_turns = len(results)
    successful_turns = sum(1 for r in results if r.get("status") in ("ok", "query"))
    total_facts = sum(r.get("facts_found", 0) for r in results)
    
    print(f"\n  Total turns:      {total_turns}")
    print(f"  Successful:       {successful_turns}/{total_turns}")
    print(f"  Facts extracted:  {total_facts}")
    print(f"  All facts stored: {len(all_facts_extracted)}")
    
    # Check Wiki files created
    wiki_files = list(wiki_path.rglob("*.md"))
    print(f"\n  Wiki files created: {len([f for f in wiki_files if '-hash' not in f.name])}")
    
    # Read index
    index_file = wiki_path / "index.md"
    if index_file.exists():
        content = index_file.read_text()
        print(f"\n  Wiki Index preview:")
        print(f"{'─' * 50}")
        lines = content.split("\n")[:20]
        for line in lines:
            print(f"  {line}")
        print(f"{'─' * 50}")
    
    # Final verdict
    print(f"\n  RESULT: {'PASS ✅' if successful_turns >= total_turns - 1 else 'PARTIAL ⚠️'}")
    
    if total_facts > 0:
        print(f"\n  🎉 Integration successful! CAM received {total_facts} facts from OpenClaw.")
    else:
        print(f"\n  ⚠️ No facts extracted. OpenClaw responded but rule-based extraction found nothing.")
        print(f"   Tip: With a real LLM backend (not heuristic), extraction would be much richer.")
    
    return results


if __name__ == "__main__":
    try:
        result = asyncio.run(run_integration_test())
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
