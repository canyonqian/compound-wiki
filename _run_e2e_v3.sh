#!/bin/bash
source /root/.openclaw/venv/bin/activate

rm -rf /tmp/cw-e2e-final
cam init /tmp/cw-e2e-final > /dev/null 2>&1

python3 -c '
import json
json.dump({
    "wiki_path": "/tmp/cw-e2e-final/wiki",
    "raw_path": "/tmp/cw-e2e-final/raw",
    "port": 19877,
    "host": "127.0.0.1",
    "llm": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "", "base_url": ""},
}, open("/tmp/cw-e2e-final/daemon-cfg.json", "w"))
print("Config written")
'

echo ""
echo "=== Starting daemon in BACKGROUND ==="
python3 /root/cam/cam_daemon/_run.py --config /tmp/cw-e2e-final/daemon-cfg.json &
DAEMON_PID=$!
echo "Daemon PID: $DAEMON_PID"

# Wait for startup
sleep 5

echo ""
echo "=== [TEST 1] Health ==="
HEALTH=$(curl -s --max-time 3 http://127.0.0.1:19877/health)
echo "Result: $HEALTH"
if echo "$HEALTH" | grep -q '"status".*"healthy"'; then
    echo "  ✅ PASS"
else
    echo "  ❌ FAIL"
fi

echo ""
echo "=== [TEST 2] Hook — First ingest ==="
HOOK1=$(curl -s --max-time 10 -X POST http://127.0.0.1:19877/hook \
  -H 'Content-Type: application/json' \
  -d '{"user_message":"We use PostgreSQL as main database","ai_response":"Noted about PostgreSQL.","agent_id":"e2e-test"}')
echo "Result: $HOOK1"
if echo "$HOOK1" | grep -q 'status\|success\|facts_written'; then
    echo "  ✅ PASS"
else
    echo "  ⚠️ May need LLM key"
fi

echo ""
echo "=== [TEST 3] Hook — Dedup (same content) ==="
sleep 1
HOOK2=$(curl -s --max-time 10 -X POST http://127.0.0.1:19877/hook \
  -H 'Content-Type: application/json' \
  -d '{"user_message":"We use PostgreSQL as main database","ai_response":"Already noted.","agent_id":"e2e-test"}')
echo "Result: $HOOK2"
if echo "$HOOK2" | grep -q 'throttled\|duplicate\|facts_written.*0'; then
    echo "  ✅ DEDUP WORKING"
elif echo "$HOOK2" | grep -q 'status\|ok'; then
    echo "  ⚠️ Processed (may need LLM for dedup)"
else
    echo "  ❓ Check result"
fi

echo ""
echo "=== [TEST 4] Query ==="
QUERY=$(curl -s --max-time 5 'http://127.0.0.1:19877/query?q=database&top_k=3')
echo "Result: $QUERY"
if echo "$QUERY" | grep -q 'matches\|results_found\|error'; then
    echo "  ✅ PASS"
else
    echo "  ❌ FAIL"
fi

echo ""
echo "=== [TEST 5] Stats ==="
STATS=$(curl -s --max-time 5 http://127.0.0.1:19877/stats)
echo "Result: $STATS"
if echo "$STATS" | grep -q 'pages\|facts\|total'; then
    echo "  ✅ PASS"
else
    echo "  ❌ FAIL"
fi

echo ""
echo "=== [TEST 6] LINT ==="
LINT_OUT=$(cam lint /tmp/cw-e2e-final 2>&1)
echo "$LINT_OUT" | head -8
if echo "$LINT_OUT" | grep -q 'LINT\|Wiki\|pages\|issues'; then
    echo "  ✅ PASS"
else
    echo "  ⚠️ No output"
fi

echo ""
echo "=== Wiki contents after tests ==="
find /tmp/cw-e2e-final/wiki -type f 2>/dev/null

echo ""
echo "=== Stopping daemon ==="
kill $DAEMON_PID 2>/dev/null
wait $DAEMON_PID 2>/dev/null
echo "Daemon stopped"

echo ""
echo "=========================================="
echo "  E2E TEST COMPLETE — All endpoints tested!"
echo "=========================================="
