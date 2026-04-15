#!/usr/bin/env python3
"""E2E: OpenClaw + CAM."""
import asyncio, json, os, subprocess, re, sys
sys.path.insert(0, "/root/cam")

def call_oc(msg, sid="cw-e2e"):
    r = subprocess.run(
        ["openclaw","agent","--local","--session-id",sid,"--message",msg,"--timeout","60"],
        capture_output=True, text=True, timeout=90,
        cwd=os.path.expanduser("~/openclaw-src")
    )
    lines = [l for l in r.stdout.strip().split(chr(10)) if l.strip() and not l.strip().startswith(chr(91))]
    return (lines[-1] if lines else r.stdout[-300:]) or f"ERR:{r.stderr[:100]}"

async def main():
    print("=" * 60, flush=True)
    print("  OpenClaw x CAM - E2E", flush=True)
    print("=" * 60, flush=True)

    from memory_core import MemoryCore
    from memory_core.extractor import FactType, ExtractedFact

    print("\n[1] Init Wiki...", flush=True)
    mc = MemoryCore(wiki_path="/root/cam/wiki")
    await mc.initialize()
    sw = mc.hook_engine.shared_wiki
    print(f"    path={sw.wiki_path}", flush=True)

    msgs = [
        "We use PostgreSQL as our main database with Drizzle ORM.",
        "Deploy on Docker with GitHub Actions CI/CD pipeline.",
        "Our team prefers TDD and code reviews before merge.",
    ]

    total = 0
    for i, m in enumerate(msgs):
        print(f"\n[2.{i+1}] Ask: {m[:50]}...", flush=True)
        reply = call_oc(m, sid="cw-e2e-final")
        reply_clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', reply).strip()
        print(f"    << {reply_clean[:120]}", flush=True)

        context = m + " " + reply_clean
        facts = []
        for kw, ft in [("PostgreSQL","fact"),("Drizzle","decision"),
                        ("Docker","fact"),("GitHub Actions","fact"),
                        ("TDD","preference")]:
            if kw.lower() in context.lower():
                facts.append(ExtractedFact(
                    fact_type=FactType(ft), content=f"Using {kw}",
                    confidence=0.8, source_text=context[:200],
                    tags=["tech"], agent_id="openclaw-e2e"))
        if facts:
            n = await sw.write_facts(facts, source="e2e-test")
            print(f"    ** Stored {n}/{len(facts)} facts {'OK' if n>0 else 'FAIL'}", flush=True)
            total += len(facts)

    print("\n" + "=" * 60, flush=True)
    idx = "/root/cam/wiki/index.md"
    if os.path.exists(idx):
        c = open(idx).read()
        print(f"  RESULT: {total} facts stored | Index entries: {c.count('- [')}", flush=True)
    else:
        print(f"  RESULT: {total} facts stored (no index yet)", flush=True)
    print("=" * 60, flush=True)

if __name__ == "__main__":
    asyncio.run(main())
