#!/bin/bash
source /root/.openclaw/venv/bin/activate

rm -rf /tmp/cw-e2e-final
cam init /tmp/cw-e2e-final > /dev/null 2>&1

python3 -c '
import json
cfg = {
    "wiki_path": "/tmp/cw-e2e-final/wiki",
    "raw_path": "/tmp/cw-e2e-final/raw",
    "port": 19877,
    "host": "127.0.0.1",
    "llm": {"provider": "openai", "model": "gpt-4o-mini", "api_key": "", "base_url": ""},
}
json.dump(cfg, open("/tmp/cw-e2e-final/daemon-cfg.json", "w"))
print("Config written")
'

echo ""
echo "=== Starting daemon (8s timeout) ==="
timeout 8 python3 /root/cam/cam_daemon/_run.py --config /tmp/cw-e2e-final/daemon-cfg.json 2>&1

echo ""
echo "=== Testing health endpoint ==="
curl -s --max-time 3 http://127.0.0.1:19877/health || echo "(connection refused or timed out)"

echo ""
echo "=== Testing hook ==="
curl -s --max-time 5 -X POST http://127.0.0.1:19877/hook \
  -H 'Content-Type: application/json' \
  -d '{"user_message":"test","ai_response":"response","agent_id":"test"}' \
  || echo "(hook failed)"

echo ""
echo "=== Wiki contents ==="
find /tmp/cw-e2e-final/wiki -type f 2>/dev/null | head -10
