#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/.."

echo "[testsuite] OpenClaw Task System 自动化测试开始"
echo "[testsuite] 项目根目录: $ROOT_DIR"

echo
echo "[testsuite] 0/4 Runtime mirror 校验"
python3 "$ROOT_DIR/scripts/runtime/runtime_mirror.py" --check

echo
echo "[testsuite] 1/4 Python runtime / CLI 回归"
python3 -m unittest discover -s "$ROOT_DIR/tests" -v

echo
echo "[testsuite] 2/4 Node plugin / control-plane 回归"
node --test "$ROOT_DIR/plugin/tests/*.test.mjs"

echo
echo "[testsuite] 3/4 Plugin Doctor 结构检查"
python3 "$ROOT_DIR/scripts/runtime/plugin_doctor.py"

echo
echo "[testsuite] 4/4 Plugin Smoke 冒烟验证"
python3 "$ROOT_DIR/scripts/runtime/plugin_smoke.py" --json

echo
echo "[testsuite] 自动化 testsuite 已全部通过"
