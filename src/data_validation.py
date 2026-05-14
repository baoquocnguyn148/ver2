import pandas as pd


REQUIRED_FACT_COLUMNS = {
    "Customer_ID",
    "Year_Quarter",
    "Year",
    "Quarter_Num",
    "Order_Count",
    "Quantity_Sold",
    "Revenue",
    "Profit",
    "Product_Line",
    "Coupon_Num",
    "Unit_Sale_Price",
}

REQUIRED_CUSTOMER_COLUMNS = {
    "Customer_ID",
    "Gender",
    "Education_Rank",
    "Income",
    "Months_As_Member",
    "Loyalty_Rank",
    "CLV",
}


def _missing_columns(df, required):
    return sorted(required - set(df.columns))


def validate_model_tables(fact, customers):
    """Return a compact data-quality report and raise on blocking schema errors."""
    issues = []
    fact_missing = _missing_columns(fact, REQUIRED_FACT_COLUMNS)
    customer_missing = _missing_columns(customers, REQUIRED_CUSTOMER_COLUMNS)

    if fact_missing:
        issues.append(("ERROR", "FACT_MISSING_COLUMNS", ", ".join(fact_missing)))
    if customer_missing:
        issues.append(("ERROR", "CUSTOMER_MISSING_COLUMNS", ", ".join(customer_missing)))

    if issues and any(level == "ERROR" for level, _, _ in issues):
        report = pd.DataFrame(issues, columns=["Level", "Check", "Detail"])
        raise ValueError(f"Blocking data validation errors:\n{report.to_string(index=False)}")

    checks = [
        ("INFO", "FACT_ROWS", len(fact)),
        ("INFO", "CUSTOMER_ROWS", len(customers)),
        ("INFO", "UNIQUE_FACT_CUSTOMERS", fact["Customer_ID"].nunique()),
        ("INFO", "UNIQUE_DIM_CUSTOMERS", customers["Customer_ID"].nunique()),
        ("WARN", "FACT_NULL_CELLS", int(fact.isna().sum().sum())),
        ("WARN", "CUSTOMER_NULL_CELLS", int(customers.isna().sum().sum())),
        ("WARN", "DUPLICATE_CUSTOMER_IDS", int(customers["Customer_ID"].duplicated().sum())),
        ("WARN", "NEGATIVE_REVENUE_ROWS", int((fact["Revenue"] < 0).sum())),
        ("WARN", "NEGATIVE_PROFIT_ROWS", int((fact["Profit"] < 0).sum())),
        ("WARN", "ORPHAN_CUSTOMER_ROWS", int((~fact["Customer_ID"].isin(customers["Customer_ID"])).sum())),
    ]
    report = pd.DataFrame(checks, columns=["Level", "Check", "Value"])
    return report

