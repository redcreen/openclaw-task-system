from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


RUNTIME_DIR = Path(__file__).resolve().parents[1] / "scripts" / "runtime"
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))


def load_runtime_module(module_name: str):
    module_path = RUNTIME_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"openclaw_task_system.{module_name}", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load runtime module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


task_state_module = load_runtime_module("task_state")
