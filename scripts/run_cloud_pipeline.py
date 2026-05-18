from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


STEPS = [
    ["data_process.py"],
    ["ml_pipeline.py"],
    ["scripts/register_glue_tables.py"],
    ["scripts/repair_athena_tables.py"],
    ["scripts/create_athena_views.py"],
    ["scripts/validate_athena.py"],
]


def main() -> None:
    env = os.environ.copy()
    env.setdefault("LOCAL_MODE", "false")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    for step in STEPS:
        command = [sys.executable, *step]
        print(f"\n=== Running: {' '.join(command)} ===", flush=True)
        subprocess.run(command, cwd=PROJECT_ROOT, env=env, check=True)


if __name__ == "__main__":
    main()
