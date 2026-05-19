from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class QualityCheck:
    check_name: str
    level: str
    status: str
    value: Any
    expected: str
    details: str = ""


def _check(
    rows: list[QualityCheck],
    check_name: str,
    passed: bool,
    value: Any,
    expected: str,
    details: str = "",
    level: str = "ERROR",
) -> None:
    rows.append(
        QualityCheck(
            check_name=check_name,
            level=level,
            status="PASS" if passed else "FAIL",
            value=value,
            expected=expected,
            details=details,
        )
    )


def _missing_columns(df: pd.DataFrame, required: set[str]) -> list[str]:
    return sorted(required - set(df.columns))


def run_quality_checks(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Run production-style quality checks over the Power BI/star-schema tables."""
    fact = tables["FACT_Sales"]
    dim_customer = tables["DIM_Customer"]
    dim_product = tables["DIM_Product"]
    dim_date = tables["DIM_Date"]
    dim_geo = tables.get("DIM_Geography")

    rows: list[QualityCheck] = []

    required_fact = {
        "Customer_ID",
        "Product_ID",
        "Date_Key",
        "Revenue",
        "Profit",
        "Quarter",
        "Year",
        "Is_Full_Year",
    }
    required_customer = {"Customer_ID"}
    required_product = {"Product_ID"}
    required_date = {"Date_Key", "Year", "Quarter"}

    for table_name, df, required in [
        ("FACT_Sales", fact, required_fact),
        ("DIM_Customer", dim_customer, required_customer),
        ("DIM_Product", dim_product, required_product),
        ("DIM_Date", dim_date, required_date),
    ]:
        missing = _missing_columns(df, required)
        _check(
            rows,
            f"{table_name}_required_columns",
            not missing,
            ", ".join(missing) if missing else "none",
            "no missing required columns",
        )

    _check(rows, "fact_sales_row_count", len(fact) > 0, len(fact), "> 0")

    if "Fact_ID" in fact.columns:
        duplicate_fact_ids = int(fact["Fact_ID"].duplicated().sum())
        _check(rows, "fact_sales_unique_fact_id", duplicate_fact_ids == 0, duplicate_fact_ids, "0 duplicates")

    natural_grain = [
        col
        for col in [
            "Customer_ID",
            "Product_ID",
            "Date_Key",
            "Geo_Key",
            "Revenue",
            "Quantity_Sold",
            "Unit_Sale_Price",
        ]
        if col in fact.columns
    ]
    if natural_grain:
        duplicate_grain_rows = int(fact.duplicated(subset=natural_grain).sum())
        _check(
            rows,
            "fact_sales_possible_duplicate_transactions",
            duplicate_grain_rows == 0,
            duplicate_grain_rows,
            "0 duplicate natural-grain rows",
            "WARNING only because the source has no immutable transaction id.",
            level="WARNING",
        )

    for column in ["Customer_ID", "Product_ID", "Date_Key"]:
        null_count = int(fact[column].isna().sum()) if column in fact.columns else len(fact)
        _check(rows, f"fact_sales_{column}_not_null", null_count == 0, null_count, "0 nulls")

    duplicate_customers = int(dim_customer["Customer_ID"].duplicated().sum())
    _check(rows, "dim_customer_unique_customer_id", duplicate_customers == 0, duplicate_customers, "0 duplicates")

    orphan_customers = int((~fact["Customer_ID"].isin(dim_customer["Customer_ID"])).sum())
    _check(rows, "fact_customer_fk_integrity", orphan_customers == 0, orphan_customers, "0 orphan rows")

    orphan_products = int((~fact["Product_ID"].isin(dim_product["Product_ID"])).sum())
    _check(rows, "fact_product_fk_integrity", orphan_products == 0, orphan_products, "0 orphan rows")

    orphan_dates = int((~fact["Date_Key"].isin(dim_date["Date_Key"])).sum())
    _check(rows, "fact_date_fk_integrity", orphan_dates == 0, orphan_dates, "0 orphan rows")

    if dim_geo is not None and {"Geo_Key"}.issubset(fact.columns) and {"Geo_Key"}.issubset(dim_geo.columns):
        orphan_geo = int((~fact["Geo_Key"].isin(dim_geo["Geo_Key"])).sum())
        _check(rows, "fact_geography_fk_integrity", orphan_geo == 0, orphan_geo, "0 orphan rows")

    negative_revenue = int((fact["Revenue"] < 0).sum())
    _check(rows, "fact_sales_no_negative_revenue", negative_revenue == 0, negative_revenue, "0 rows")

    negative_profit = int((fact["Profit"] < 0).sum())
    _check(rows, "fact_sales_no_negative_profit", negative_profit == 0, negative_profit, "0 rows")

    invalid_quarters = sorted(set(fact["Quarter"].dropna()) - {"Q1", "Q2", "Q3", "Q4"})
    _check(
        rows,
        "fact_sales_accepted_quarter_values",
        not invalid_quarters,
        ", ".join(map(str, invalid_quarters)) if invalid_quarters else "none",
        "Q1, Q2, Q3, Q4 only",
    )

    has_2020_rows = bool((fact["Year"] == 2020).any())
    has_partial_year_flag = "Is_Full_Year" in fact.columns
    partial_2020_ok = (
        has_2020_rows
        and has_partial_year_flag
        and bool((fact.loc[fact["Year"] == 2020, "Is_Full_Year"] == False).all())
    )
    _check(
        rows,
        "fact_sales_2020_partial_year_flag",
        partial_2020_ok,
        "present" if partial_2020_ok else "missing_or_invalid",
        "2020 rows exist and Is_Full_Year=false",
    )

    if "Year" in fact.columns:
        max_year = int(fact["Year"].max())
        _check(
            rows,
            "fact_sales_recent_year_warning",
            max_year >= 2020,
            max_year,
            ">= 2020",
            "WARNING only: protects scheduled runs from accidentally loading stale raw files.",
            level="WARNING",
        )

    report = pd.DataFrame([row.__dict__ for row in rows])
    return report


def has_blocking_failures(report: pd.DataFrame) -> bool:
    return bool(((report["level"] == "ERROR") & (report["status"] == "FAIL")).any())
