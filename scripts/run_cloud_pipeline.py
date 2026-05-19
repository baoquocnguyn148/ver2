from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_RETRIES = 1
NETWORK_RETRIES = 3
RETRY_BACKOFF_SECONDS = 10


@dataclass(frozen=True)
class PipelineStep:
    name: str
    args: list[str]
    attempts: int = DEFAULT_RETRIES


STEPS = [
    PipelineStep("ETL star schema and curated parquet", ["data_process.py"]),
    PipelineStep("Data quality checks", ["scripts/run_data_quality.py"]),
    PipelineStep("ML forecast and churn pipeline", ["ml_pipeline.py"]),
    PipelineStep("Register Glue external tables", ["scripts/register_glue_tables.py"], NETWORK_RETRIES),
    PipelineStep("Repair Athena partitions", ["scripts/repair_athena_tables.py"], NETWORK_RETRIES),
    PipelineStep("Create Athena views", ["scripts/create_athena_views.py"], NETWORK_RETRIES),
    PipelineStep("Validate Athena tables and views", ["scripts/validate_athena.py"], NETWORK_RETRIES),
]


def _run_step(step: PipelineStep, env: dict[str, str]) -> float:
    command = [sys.executable, *step.args]
    started = time.perf_counter()
    for attempt in range(1, step.attempts + 1):
        print(
            f"\n=== Running: {step.name} "
            f"(attempt {attempt}/{step.attempts}) ===",
            flush=True,
        )
        print(f"Command: {' '.join(command)}", flush=True)
        try:
            subprocess.run(command, cwd=PROJECT_ROOT, env=env, check=True)
            duration = time.perf_counter() - started
            print(f"=== Completed: {step.name} in {duration:.1f}s ===", flush=True)
            return duration
        except subprocess.CalledProcessError:
            if attempt >= step.attempts:
                duration = time.perf_counter() - started
                print(f"=== Failed: {step.name} after {duration:.1f}s ===", flush=True)
                raise
            sleep_seconds = RETRY_BACKOFF_SECONDS * attempt
            print(
                f"Step failed. Retrying in {sleep_seconds}s "
                f"to absorb transient AWS/network failures...",
                flush=True,
            )
            time.sleep(sleep_seconds)
    raise RuntimeError(f"Unreachable retry state for step: {step.name}")


def main() -> None:
    env = os.environ.copy()
    env.setdefault("LOCAL_MODE", "false")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    total_started = time.perf_counter()
    timings = []
    for step in STEPS:
        timings.append((step.name, _run_step(step, env)))

    print("\n=== Pipeline Timing Summary ===", flush=True)
    for name, duration in timings:
        print(f"{duration:8.1f}s  {name}", flush=True)
    print(f"{time.perf_counter() - total_started:8.1f}s  TOTAL", flush=True)


if __name__ == "__main__":
    main()
