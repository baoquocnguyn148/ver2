from __future__ import annotations

import sys
from pathlib import Path

import awswrangler as wr

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import config


TABLES = {
    "fact_sales": {
        "path": f"s3://{config.S3_BUCKET}/{config.CURATED_PREFIX.strip('/')}/fact_sales/",
        "partition_cols": ["partition_year"],
    },
    "dim_customer": {
        "path": f"s3://{config.S3_BUCKET}/{config.CURATED_PREFIX.strip('/')}/dim_customer/",
        "partition_cols": ["partition_loyalty_status"],
    },
    "dim_product": {
        "path": f"s3://{config.S3_BUCKET}/{config.CURATED_PREFIX.strip('/')}/dim_product/",
        "partition_cols": [],
    },
    "dim_date": {
        "path": f"s3://{config.S3_BUCKET}/{config.CURATED_PREFIX.strip('/')}/dim_date/",
        "partition_cols": ["partition_year"],
    },
    "dim_geography": {
        "path": f"s3://{config.S3_BUCKET}/{config.CURATED_PREFIX.strip('/')}/dim_geography/",
        "partition_cols": ["partition_country"],
    },
}


def _athena_type(dtype) -> str:
    text = str(dtype).lower()
    if text.startswith("int") or text.startswith("uint"):
        return "bigint"
    if text.startswith("float"):
        return "double"
    if text.startswith("bool"):
        return "boolean"
    if text.startswith("datetime"):
        return "timestamp"
    return "string"


def _sample_schema(path: str):
    """Read a small Parquet chunk to infer dtypes without loading the full dataset."""
    chunks = wr.s3.read_parquet(path=path, dataset=True, chunked=500)
    try:
        return next(chunks)
    except StopIteration:
        import pandas as pd

        return pd.DataFrame()


def main() -> None:
    print(f"Registering Glue tables in database: {config.ATHENA_DATABASE}")
    for table_name, spec in TABLES.items():
        sample = _sample_schema(spec["path"])
        partition_cols = set(spec["partition_cols"])
        columns_types = {
            col: _athena_type(dtype)
            for col, dtype in sample.dtypes.items()
            if col not in partition_cols
        }
        partitions_types = {col: "string" for col in partition_cols}
        wr.catalog.create_parquet_table(
            database=config.ATHENA_DATABASE,
            table=table_name,
            path=spec["path"],
            columns_types=columns_types,
            partitions_types=partitions_types or None,
            mode="overwrite",
        )
        print(
            f"  OK: {table_name:<16} "
            f"({len(columns_types)} columns, {len(partitions_types)} partition(s))"
        )


if __name__ == "__main__":
    main()
