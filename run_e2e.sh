#!/bin/bash
# E2E Test Runner for OpenClaw + Compound Wiki
cd ~/compound-wiki

echo "=== Step 1: Quick Python check ==="
python3 -u -c "print('Python works', flush=True)"
if [ $? -ne 0 ]; then echo "Python broken!"; exit 1; fi

echo ""
echo "=== Step 2: MemoryCore import test ==="
python3 -u -c "
import sys; sys.path.insert(0, '.')
from memory_core import MemoryCore
print('Import OK', flush=True)
"
if [ $? -ne 0 ]; then echo "Import broken!"; exit 1; fi

echo ""
echo "=== Step 3: Single OpenClaw call ==="
cd ~/openclaw-src
RESULT=$(openclaw agent --local --session-id cw-verify --message 'Say OK' --timeout 30 2>&1 | grep -v '^\[' | tail -1)
echo "OpenClaw replied: $RESULT"

echo ""
echo "=== Step 4: Full E2E test ==="
cd ~/compound-wiki
python3 -u memory_core/examples/e2e_simple.py 2>&1
echo ""
echo "=== DONE (exit code: $?) ==="
