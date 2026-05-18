import pandas as pd

from . import config
from .config import CUSTOMER_SHEET, DATA_MODEL_FILE, FACT_SHEET
from .utils.io_utils import DataIO


def load_model_tables(path=DATA_MODEL_FILE):
    """Load the processed Power BI data model required by the ML pipeline."""
    if path.exists():
        print(f"[DataLoading] Reading processed model from local path: {path}")
        fact = pd.read_excel(path, sheet_name=FACT_SHEET)
        customers = pd.read_excel(path, sheet_name=CUSTOMER_SHEET)
        return fact, customers

    if not config.LOCAL_MODE:
        processed_key = f"{config.OUTPUT_PREFIX.strip('/')}/data_model.xlsx"
        print(f"[DataLoading] Local data model not found, reading from s3://{config.S3_BUCKET}/{processed_key}")
        io = DataIO()
        fact = io.read_excel(processed_key, sheet_name=FACT_SHEET)
        customers = io.read_excel(processed_key, sheet_name=CUSTOMER_SHEET)
        return fact, customers

    raise FileNotFoundError(f"Processed data model not found: {path}")


def add_quarter_index(fact):
    """Create a stable quarter index from Year_Quarter."""
    fact = fact.copy()
    quarter_order = (
        fact[["Year_Quarter", "Year", "Quarter_Num"]]
        .drop_duplicates()
        .sort_values(["Year", "Quarter_Num"])
        .reset_index(drop=True)
    )
    quarter_order["Quarter_Idx"] = range(1, len(quarter_order) + 1)
    idx_map = quarter_order.set_index("Year_Quarter")["Quarter_Idx"].to_dict()
    fact["Quarter_Idx"] = fact["Year_Quarter"].map(idx_map).astype(int)
    return fact, quarter_order
