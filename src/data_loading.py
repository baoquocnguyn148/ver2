import pandas as pd

from .config import CUSTOMER_SHEET, DATA_MODEL_FILE, FACT_SHEET


def load_model_tables(path=DATA_MODEL_FILE):
    """Load the processed Power BI data model required by the ML pipeline."""
    fact = pd.read_excel(path, sheet_name=FACT_SHEET)
    customers = pd.read_excel(path, sheet_name=CUSTOMER_SHEET)
    return fact, customers


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

