#!/usr/bin/env bash
set -euo pipefail

REPO_SLUG="${OPENCLAW_TASK_SYSTEM_REPO:-redcreen/openclaw-task-system}"
REF="${OPENCLAW_TASK_SYSTEM_REF:-v0.1.0}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
OPENCLAW_BIN="${OPENCLAW_BIN:-openclaw}"
TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

echo "[openclaw-task-system] downloading ${REPO_SLUG}@${REF}"

archive_url=""
if [[ "${REF}" == v* ]]; then
  archive_url="https://github.com/${REPO_SLUG}/archive/refs/tags/${REF}.tar.gz"
else
  archive_url="https://github.com/${REPO_SLUG}/archive/refs/heads/${REF}.tar.gz"
fi

curl -fsSL "${archive_url}" -o "${TMP_DIR}/repo.tar.gz"
tar -xzf "${TMP_DIR}/repo.tar.gz" -C "${TMP_DIR}"

repo_dir="$(find "${TMP_DIR}" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
if [[ -z "${repo_dir}" ]]; then
  echo "[openclaw-task-system] failed to extract repository archive" >&2
  exit 1
fi

cd "${repo_dir}"

echo "[openclaw-task-system] verifying canonical runtime mirror"
"${PYTHON_BIN}" scripts/runtime/runtime_mirror.py --check >/dev/null

echo "[openclaw-task-system] validating plugin bundle"
"${PYTHON_BIN}" scripts/runtime/plugin_doctor.py >/dev/null

echo "[openclaw-task-system] installing plugin"
"${OPENCLAW_BIN}" plugins install ./plugin

echo "[openclaw-task-system] writing minimal plugin config"
"${PYTHON_BIN}" scripts/runtime/configure_openclaw_plugin.py --write

echo "[openclaw-task-system] running post-install smoke"
"${PYTHON_BIN}" scripts/runtime/plugin_smoke.py >/dev/null

echo
echo "[openclaw-task-system] install complete"
echo
echo "next checks:"
echo "  ${PYTHON_BIN} scripts/runtime/main_ops.py dashboard --json"
echo "  ${PYTHON_BIN} scripts/runtime/stable_acceptance.py --json"
echo
echo "default install track: ${REF}"
if [[ "${REF}" == "main" ]]; then
  echo "mode: development / main branch"
else
  echo "mode: stable tagged release"
fi
