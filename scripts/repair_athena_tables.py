from __future__ import annotations

import sys
import time
from pathlib import Path

import boto3

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import config

MAX_WAIT_SECONDS = 300

TABLES = ["fact_sales", "dim_customer", "dim_product", "dim_date", "dim_geography"]


def _run_query(client, query: str) -> str:
    response = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": config.ATHENA_DATABASE},
        ResultConfiguration={"OutputLocation": config.ATHENA_OUTPUT},
        WorkGroup=config.ATHENA_WORKGROUP,
    )
    return response["QueryExecutionId"]


def _wait_for_query(client, query_id: str) -> None:
    start = time.time()
    while True:
        if time.time() - start > MAX_WAIT_SECONDS:
            raise TimeoutError(
                f"Athena query {query_id} exceeded {MAX_WAIT_SECONDS}s timeout"
            )
        response = client.get_query_execution(QueryExecutionId=query_id)
        status = response["QueryExecution"]["Status"]["State"]
        if status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            if status != "SUCCEEDED":
                reason = response["QueryExecution"]["Status"].get("StateChangeReason", "")
                raise RuntimeError(f"Athena query {query_id} {status}: {reason}")
            return
        time.sleep(2)


def main() -> None:
    client = boto3.client("athena")
    print(f"Repairing Athena partitions in: {config.ATHENA_DATABASE} (workgroup: {config.ATHENA_WORKGROUP})")
    print(f"Query results: {config.ATHENA_OUTPUT}")

    for table in TABLES:
        query = f"MSCK REPAIR TABLE {table}"
        print(f"  Running: {query}")
        query_id = _run_query(client, query)
        _wait_for_query(client, query_id)
        print(f"  OK: {table}")


if __name__ == "__main__":
    main()
