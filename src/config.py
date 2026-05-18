import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional during minimal local runs
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if load_dotenv is not None:
    load_dotenv(PROJECT_ROOT / ".env")


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


LOCAL_MODE = _env_bool("LOCAL_MODE", True)
S3_BUCKET = os.getenv("S3_BUCKET", "ver2-retail-analytics")
RAW_KEY = os.getenv("RAW_KEY", "raw/DB.xlsx")
CURATED_PREFIX = os.getenv("CURATED_PREFIX", "curated/")
OUTPUT_PREFIX = os.getenv("OUTPUT_PREFIX", "outputs/")
ATHENA_DATABASE = os.getenv("ATHENA_DATABASE", "retail_analytics")
ATHENA_OUTPUT = os.getenv(
    "ATHENA_OUTPUT",
    f"s3://{S3_BUCKET}/{OUTPUT_PREFIX.strip('/')}/athena/",
)

WORK_DIR = PROJECT_ROOT if LOCAL_MODE else Path(os.getenv("WORK_DIR", "/tmp/ver2"))
WORK_DIR.mkdir(parents=True, exist_ok=True)

DATA_MODEL_FILE = WORK_DIR / "data_model.xlsx"
OUTPUT_DIR = WORK_DIR / "outputs"
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
