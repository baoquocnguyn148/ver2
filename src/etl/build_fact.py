from __future__ import annotations

import pandas as pd


def prepare_fact_for_curated(fact_sales: pd.DataFrame) -> pd.DataFrame:
    """Add partition metadata to the sales fact before writing curated Parquet."""
    curated = fact_sales.copy()
    curated["partition_year"] = curated["Year"].astype(str)
    return curated

