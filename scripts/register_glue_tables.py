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


def main() -> None:
    print(f"Registering Glue tables in database: {config.ATHENA_DATABASE}")
    for table_name, spec in TABLES.items():
        df = wr.s3.read_parquet(path=spec["path"], dataset=True, path_suffix=".parquet")
        partition_cols = set(spec["partition_cols"])
        columns_types = {
            column: _athena_type(dtype)
            for column, dtype in df.dtypes.items()
            if column not in partition_cols
        }
        partitions_types = {column: "string" for column in partition_cols}
        wr.catalog.create_parquet_table(
            database=config.ATHENA_DATABASE,
            table=table_name,
            path=spec["path"],
            columns_types=columns_types,
            partitions_types=partitions_types or None,
            mode="overwrite",
        )
        print(
            f"  OK: {table_name} "
            f"({len(columns_types)} columns, {len(partitions_types)} partitions)"
        )


if __name__ == "__main__":
    main()
