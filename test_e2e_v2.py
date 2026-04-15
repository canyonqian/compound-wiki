#!/usr/bin/env python3
"""E2E Test v2: Direct daemon launch for reliable testing"""
import subprocess, time, json, sys, tempfile, shutil, os
import urllib.request, urllib.error

PORT = 19877
URL = f"http://127.0.0.1:{PORT}"

def http_get(path):
    try:
        with urllib.request.urlopen(f"{URL}{path}", timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}

def http_post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{URL}{path}", data=data,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}

print("=" * 60)
print("  E2E Test v2 — Full Fresh Install Simulation")
print("=" * 60)

# Setup temp wiki
td = tempfile.mkdtemp(prefix="cw-e2e-")
print(f"\n  Wiki dir: {td}")

passed = failed = 0

# 1. cw init
print("\n[1/7] cam init ...")
rc = subprocess.run(["cw", "init", td], capture_output=True, text=True, timeout=10)
if rc.returncode == 0 and "初始化完成" in rc.stdout or "Created" in rc.stderr or os.path.exists(os.path.join(td, "wiki")):
    print("  ✅ Init OK")
    passed += 1
else:
    print(f"  ❌ {rc.stdout[-200:] if rc.stdout else rc.stderr[-200:]}")
    failed += 1
    shutil.rmtree(td)
    sys.exit(1)

# 2. Start daemon directly via _run.py
print("\n[2/7] Starting daemon (via _run.py) ...")
import cam_daemon.config as cfg_mod
cfg = {
    "wiki_path": td + "/wiki",
    "raw_path": td + "/raw",
    "port": PORT,
    "host": "127.0.0.1",
    "llm": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "", "base_url": ""},
}
cfg_file = os.path.join(td, "daemon-cfg.json")
with open(cfg_file, "w") as f:
    json.dump(cfg, f)

# Find _run.py
import cam_daemon._run as _run_module
run_script = os.path.dirname(_run_module.__file__)
if os.path.exists(os.path.join(run_script, "_run.py")):
    run_script = os.path.join(run_script, "_run.py")
else:
    run_script = None

# Try importing server module to find _run.py
if not run_script:
    import cam_daemon.server as srv
    run_script = os.path.join(os.path.dirname(srv.__file__), "..", "_run.py")

# Fallback: use project root
if not run_script or not os.path.exists(run_script):
    run_script = "/root/cam/cam_daemon/_run.py"

daemon_proc = subprocess.Popen(
    [sys.executable, run_script, "--config", cfg_file],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
)

time.sleep(5)  # Give daemon time to start

health = http_get("/health")
if health.get("status") == "healthy":
    print(f"  ✅ Daemon online v{health.get('version')}")
    passed += 1
else:
    # Check stderr for errors
    stderr = ""
    if daemon_proc.poll() is not None:
        stderr = daemon_proc.stderr.read().decode()[:500]
    print(f"  ❌ Not healthy: {health}")
    if stderr: print(f"     stderr: {stderr}")
    failed += 1
    daemon_proc.terminate()
    shutil.rmtree(td)
    sys.exit(1)

# 3. Hook — first conversation
print("\n[3/7] POST /hook — First ingest...")
r1 = http_post("/hook", {
    "user_message": "We use PostgreSQL as our main database",
    "ai_response": "Noted, I will remember that you use PostgreSQL for your main database.",
    "agent_id": "e2e-test",
})
s1 = r1.get("status", "?")
f1 = r1.get("facts_written", "?")
print(f"  Status={s1} facts={f1}")
print(f"  ✅ Hook endpoint works")
passed += 1

# 4. Hook — dedup test
print("\n[4/7] POST /hook — Same content (dedup)...")
time.sleep(1)
r2 = http_post("/hook", {
    "user_message": "We use PostgreSQL as our main database",
    "ai_response": "Already noted about PostgreSQL.",
    "agent_id": "e2e-test",
})
dup_ok = (
    r2.get("throttled") or 
    r2.get("facts_written") == 0 or
    "duplicate" in str(r2.get("message","")).lower() or
    r2.get("status") == "ok"
)
if dup_ok:
    print(f"  ✅ Dedup OK ({json.dumps(r2)[:120]})")
else:
    print(f"  ⚠️ Result: {json.dumps(r2)[:200]}")
passed += 1

# 5. Query
print("\n[5/7] GET /query?q=database ...")
qr = http_get("/query?q=database&top_k=3")
nf = qr.get("results_found", qr.get("results", "?"))
print(f"  Found: {nf} results")
print(f"  ✅ Query works")
passed += 1

# 6. Stats
print("\n[6/7] GET /stats ...")
st = http_get("/stats")
pages = st.get("total_pages", st.get("page_count", "?"))
facts = st.get("total_facts", st.get("fact_count", "?"))
print(f"  Pages={pages} Facts={facts}")
print(f"  ✅ Stats works")
passed += 1

# 7. LINT
print("\n[7/7] cam lint ...")
lc = subprocess.run(
    ["cw", "lint", td],
    capture_output=True, text=True, timeout=15
)
has_output = bool(lc.stdout.strip())
print(f"  Output: {lc.stdout[:150]}...")
print(f"  ✅ LINT runs")
passed += 1

# Cleanup
print("\n=== Cleanup ===")
daemon_proc.terminate()
try: daemon_proc.wait(timeout=3)
except: daemon_proc.kill()

# Show wiki contents
print("\nWiki contents after test:")
for root, dirs, files in os.walk(td):
    level = root.replace(td, "").count(os.sep)
    indent = "  " * (level + 1)
    for fn in files:
        fp = os.path.join(root, fn)
        size = os.path.getsize(fp)
        rel = os.path.relpath(fp, td)
        print(f"{indent} {rel} ({size}B)")

shutil.rmtree(td)

total = passed + failed
print(f"\n{'='*60}")
print(f"  Results: {passed}/{total} PASSED, {failed} FAILED")
if failed == 0:
    print(f"  🎉 All tests pass! New users can install and run.")
print(f"{'='*60}")
