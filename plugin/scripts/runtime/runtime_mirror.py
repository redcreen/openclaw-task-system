#!/usr/bin/env python3
from __future__ import annotations

import filecmp
import json
import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_RUNTIME_DIR = PROJECT_ROOT / "scripts" / "runtime"
PLUGIN_RUNTIME_MIRROR_DIR = PROJECT_ROOT / "plugin" / "scripts" / "runtime"


def _iter_runtime_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        if path.suffix == ".pyc":
            continue
        files.append(path.relative_to(root))
    return files


def build_runtime_mirror_report(
    *,
    canonical_dir: Path = CANONICAL_RUNTIME_DIR,
    mirror_dir: Path = PLUGIN_RUNTIME_MIRROR_DIR,
) -> dict[str, object]:
    canonical_files = _iter_runtime_files(canonical_dir)
    mirror_files = _iter_runtime_files(mirror_dir)
    canonical_set = set(canonical_files)
    mirror_set = set(mirror_files)
    missing_in_mirror = sorted(path.as_posix() for path in canonical_set - mirror_set)
    extra_in_mirror = sorted(path.as_posix() for path in mirror_set - canonical_set)
    changed_files = sorted(
        path.as_posix()
        for path in canonical_set & mirror_set
        if not filecmp.cmp(canonical_dir / path, mirror_dir / path, shallow=False)
    )
    mirror_exists = mirror_dir.exists()
    return {
        "ok": mirror_exists and not missing_in_mirror and not extra_in_mirror and not changed_files,
        "canonical_runtime_dir": str(canonical_dir),
        "mirror_runtime_dir": str(mirror_dir),
        "mirror_runtime_exists": mirror_exists,
        "canonical_file_count": len(canonical_files),
        "mirror_file_count": len(mirror_files),
        "missing_in_mirror": missing_in_mirror,
        "extra_in_mirror": extra_in_mirror,
        "changed_files": changed_files,
    }


def sync_runtime_mirror(
    *,
    canonical_dir: Path = CANONICAL_RUNTIME_DIR,
    mirror_dir: Path = PLUGIN_RUNTIME_MIRROR_DIR,
) -> dict[str, object]:
    report_before = build_runtime_mirror_report(canonical_dir=canonical_dir, mirror_dir=mirror_dir)
    mirror_dir.mkdir(parents=True, exist_ok=True)
    canonical_files = _iter_runtime_files(canonical_dir)
    for relative in canonical_files:
        source = canonical_dir / relative
        target = mirror_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for relative_text in report_before["extra_in_mirror"]:
        target = mirror_dir / relative_text
        if target.exists():
            target.unlink()
    report_after = build_runtime_mirror_report(canonical_dir=canonical_dir, mirror_dir=mirror_dir)
    report_after["synced"] = True
    return report_after


def render_markdown(payload: dict[str, object]) -> str:
    return "\n".join(
        [
            "# Runtime Mirror",
            "",
            f"- ok: {payload.get('ok')}",
            f"- canonical_runtime_dir: {payload.get('canonical_runtime_dir')}",
            f"- mirror_runtime_dir: {payload.get('mirror_runtime_dir')}",
            f"- mirror_runtime_exists: {payload.get('mirror_runtime_exists')}",
            f"- canonical_file_count: {payload.get('canonical_file_count')}",
            f"- mirror_file_count: {payload.get('mirror_file_count')}",
            f"- missing_in_mirror: {', '.join(payload.get('missing_in_mirror', [])) or 'none'}",
            f"- extra_in_mirror: {', '.join(payload.get('extra_in_mirror', [])) or 'none'}",
            f"- changed_files: {', '.join(payload.get('changed_files', [])) or 'none'}",
            "",
        ]
    )


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--write" in args:
        payload = sync_runtime_mirror()
    else:
        payload = build_runtime_mirror_report()
    if "--json" in args:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload), end="")
    if "--check" in args and not bool(payload.get("ok")):
        raise SystemExit(1)
