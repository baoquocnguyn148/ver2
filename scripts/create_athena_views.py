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
DB = config.ATHENA_DATABASE
SQL_DIR = PROJECT_ROOT / "sql" / "views"

VIEW_ORDER = [
    "sales_by_product",
    "sales_by_quarter",
    "sales_by_loyalty",
    "customer_value",
    "retention_priority",
    "churn_priority_customers",
]


def _run_query(client, statement: str) -> str:
    response = client.start_query_execution(
        QueryString=statement,
        QueryExecutionContext={"Database": config.ATHENA_DATABASE},
        ResultConfiguration={"OutputLocation": config.ATHENA_OUTPUT},
        WorkGroup=config.ATHENA_WORKGROUP,
    )
    query_id = response["QueryExecutionId"]
    start = time.time()
    while True:
        if time.time() - start > MAX_WAIT_SECONDS:
            raise TimeoutError(f"Athena query {query_id} exceeded {MAX_WAIT_SECONDS}s")
        status = client.get_query_execution(QueryExecutionId=query_id)["QueryExecution"]["Status"]
        state = status["State"]
        if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            if state != "SUCCEEDED":
                reason = status.get("StateChangeReason", "")
                raise RuntimeError(f"Athena query {query_id} {state}: {reason}")
            return query_id
        time.sleep(1)


def _read_view_sql(view_name: str) -> str:
    path = SQL_DIR / f"{view_name}.sql"
    if not path.exists():
        raise FileNotFoundError(f"Missing SQL view definition: {path}")
    return path.read_text(encoding="utf-8").format(db=DB).strip().rstrip(";")


def main() -> None:
    client = boto3.client("athena")
    print(f"Creating Athena SQL views in: {DB} (workgroup: {config.ATHENA_WORKGROUP})")

    for view_name in reversed(VIEW_ORDER):
        statement = f"DROP VIEW IF EXISTS {DB}.{view_name}"
        query_id = _run_query(client, statement)
        print(f"  DROP: {view_name:<24} ({query_id})")

    for view_name in VIEW_ORDER:
        statement = _read_view_sql(view_name)
        query_id = _run_query(client, statement)
        print(f"  CREATE: {view_name:<22} ({query_id})")


if __name__ == "__main__":
    main()
