#!/usr/bin/env python3
"""新用户安装验证脚本 — 模拟从 GitHub 克隆后的完整测试"""
import importlib
import subprocess
import sys

print("=" * 60)
print("  CAM v2.0 — 新用户安装验证")
print("=" * 60)

# 1. 模块导入测试
print("\n[1/4] 模块导入测试")
modules = [
    "memory_core",
    "memory_core.shared_wiki",
    "memory_core.deduplicator",
    "cam_daemon",
    "cam_daemon.server",
    "cam_daemon.config",
    "cam_daemon.client",
    "cam_daemon.scheduler",
    "cam.cli",
]
ok = 0
fail = 0
for m in modules:
    try:
        importlib.import_module(m)
        print(f"  ✅ {m}")
        ok += 1
    except Exception as e:
        print(f"  ❌ {m}: {e}")
        fail += 1

# 2. CLI 命令检查
print(f"\n[2/4] CLI 命令 (结果: {ok}/{len(modules)} 通过)")
r = subprocess.run(["cw", "--help"], capture_output=True, text=True, timeout=10)
if r.returncode == 0:
    print("  ✅ cam --help OK")
    for line in r.stdout.split("\n"):
        s = line.strip()
        if s.startswith("[") or any(kw in s.lower() for kw in ["daemon", "ingest", "query", "lint", "init"]):
            print(f"     {s}")
else:
    print(f"  ❌ cam --help failed: {r.stderr[:200]}")

# 3. daemon 子命令检查
print("\n[3/4] Daemon 子命令")
r = subprocess.run(["cw", "daemon", "--help"], capture_output=True, text=True, timeout=10)
if r.returncode == 0:
    print("  ✅ cam daemon --help OK")
    for line in r.stdout.split("\n"):
        s = line.strip()
        if s in ["start", "stop", "restart", "status", "ping"]:
            print(f"     {s}")
else:
    print(f"  ❌ cam daemon --help failed: {r.stderr[:200]}")

# 4. LINT 健康检查（如果有 wiki 目录）
print("\n[4/4] LINT 健康检查")
r = subprocess.run(
    ["cw", "lint", "--wiki-dir", "/root/cam/wiki"],
    capture_output=True, text=True, timeout=15
)
if r.returncode == 0:
    print("  ✅ cam lint OK")
    if r.stdout.strip():
        print(r.stdout.strip())
else:
    # lint 可能返回非零（有 warning）
    print(f"  ⚠️ cam lint: {r.stdout[:300] or r.stderr[:300]}")

print(f"\n{'=' * 60}")
print(f"  结果: {ok}/{len(modolds)} 模块通过, {fail} 失败")
print(f"{'=' * 60}")
