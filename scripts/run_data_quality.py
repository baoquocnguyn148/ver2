from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import config
from src.etl.data_quality import has_blocking_failures, run_quality_checks
from src.utils.io_utils import DataIO

SHEETS = ["FACT_Sales", "DIM_Customer", "DIM_Product", "DIM_Date", "DIM_Geography"]


def _resolve_data_model_path() -> Path:
    candidates = [config.DATA_MODEL_FILE, config.PROJECT_ROOT / "data_model.xlsx"]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "data_model.xlsx not found. Run data_process.py before scripts/run_data_quality.py."
    )


def main() -> None:
    data_model_path = _resolve_data_model_path()
    print(f"Running data quality checks from: {data_model_path}")

    tables = {
        sheet_name: pd.read_excel(data_model_path, sheet_name=sheet_name)
        for sheet_name in SHEETS
    }
    report = run_quality_checks(tables)

    io = DataIO()
    output_location = io.save_csv("data_quality_report.csv", report, prefix=config.OUTPUT_PREFIX)

    print(report.to_string(index=False))
    print(f"\nData quality report: {output_location}")

    if has_blocking_failures(report):
        raise SystemExit("Blocking data quality failures detected.")

    print("Data quality checks passed.")


if __name__ == "__main__":
    main()

