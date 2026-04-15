#!/usr/bin/env python3
import json, os, sys, subprocess, time, urllib.request, urllib.error

PORT = 19877
URL = f"http://127.0.0.1:{PORT}"
td = "/tmp/cw-e2e-final"

def get(path):
    try:
        with urllib.request.urlopen(f"{URL}{path}", timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}

def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{URL}{path}", data=data,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}

# Write config
cfg = {
    "wiki_path": td + "/wiki",
    "raw_path": td + "/raw",
    "port": PORT,
    "host": "127.0.0.1",
    "llm": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "", "base_url": ""},
}
with open(td + "/daemon-cfg.json", "w") as f:
    json.dump(cfg, f)

print("Config written")
print("Wiki exists:", os.path.exists(td + "/wiki"))

# Start daemon
run_script = "/root/cam/cam_daemon/_run.py"
if not os.path.exists(run_script):
    # Try finding via module
    import cam_daemon._run as m
    run_script = m.__file__

print("Run script:", run_script)

proc = subprocess.Popen(
    [sys.executable, run_script, "--config", td + "/daemon-cfg.json"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
)
print(f"Daemon PID: {proc.pid}")

time.sleep(5)

health = get("/health")
print(f"Health: {json.dumps(health)}")

if health.get("status") != "healthy":
    stderr = proc.stderr.read().decode()[:500] if proc.poll() is not None else ""
    print(f"Daemon stderr: {stderr}")
    proc.terminate()
    sys.exit(1)

print("\n=== Daemon is running! ===\n")

# Hook test 1
r1 = post("/hook", {
    "user_message": "We use PostgreSQL as our main database",
    "ai_response": "Noted, I will remember that you use PostgreSQL for your main database.",
    "agent_id": "e2e-test",
})
print(f"Hook 1: {json.dumps(r1)[:200]}")

# Hook test 2 (dedup)
time.sleep(1)
r2 = post("/hook", {
    "user_message": "We use PostgreSQL as our main database",
    "ai_response": "Already noted about PostgreSQL.",
    "agent_id": "e2e-test",
})
print(f"Hook 2 (dedup): {json.dumps(r2)[:200]}")

# Query
qr = get("/query?q=database&top_k=3")
print(f"Query: {json.dumps(qr)[:200]}")

# Stats
st = get("/stats")
print(f"Stats: {json.dumps(st)[:300]}")

# LINT
lc = subprocess.run(["cw", "lint", td], capture_output=True, text=True, timeout=15)
print(f"Lint exit={lc.returncode}")
print(lc.stdout[:200] or lc.stderr[:200])

# Show wiki files
print("\n=== Wiki contents ===")
for root, dirs, files in os.walk(td):
    level = root.replace(td, "").count(os.sep)
    indent = "  " * (level + 1)
    for fn in files:
        fp = os.path.join(root, fn)
        size = os.path.getsize(fp)
        rel = os.path.relpath(fp, td)
        print(f"{indent} {rel} ({size}B)")

proc.terminate()

print("\n✅ E2E TEST COMPLETE")
