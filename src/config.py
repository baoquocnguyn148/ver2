from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_MODEL_FILE = PROJECT_ROOT / "data_model.xlsx"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
MODEL_DIR = OUTPUT_DIR / "models"
REPORT_DIR = OUTPUT_DIR / "reports"

FACT_SHEET = "FACT_Sales"
CUSTOMER_SHEET = "DIM_Customer"

FORECAST_HORIZON = [
    ("2020-Q2", 18, 2),
    ("2020-Q3", 19, 3),
    ("2020-Q4", 20, 4),
    ("2021-Q1", 21, 1),
    ("2021-Q2", 22, 2),
    ("2021-Q3", 23, 3),
    ("2021-Q4", 24, 4),
]

RANDOM_SEED = 42

