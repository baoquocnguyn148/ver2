from __future__ import annotations

import pandas as pd


def prepare_customer_for_curated(dim_customer: pd.DataFrame) -> pd.DataFrame:
    """Add loyalty partition metadata to the customer dimension."""
    curated = dim_customer.copy()
    curated["partition_loyalty_status"] = curated["LoyaltyStatus"].astype(str)
    return curated


def prepare_date_for_curated(dim_date: pd.DataFrame) -> pd.DataFrame:
    """Add year partition metadata to the date dimension."""
    curated = dim_date.copy()
    curated["partition_year"] = curated["Year"].astype(str)
    return curated


def prepare_geography_for_curated(dim_geography: pd.DataFrame) -> pd.DataFrame:
    """Add country partition metadata to the geography dimension."""
    curated = dim_geography.copy()
    curated["partition_country"] = curated["Country"].astype(str)
    return curated

