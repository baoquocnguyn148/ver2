from __future__ import annotations

import sys
import time
from pathlib import Path

import boto3

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import config

MAX_WAIT_SECONDS = 120
QUERY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 3
DB = config.ATHENA_DATABASE

QUERIES = {
    "fact_sales": f"SELECT count(*) AS rows FROM {DB}.fact_sales",
    "fact_sales_freshness": (
        f"SELECT min(year_quarter) AS min_quarter, max(year_quarter) AS max_quarter, "
        f"count(DISTINCT year_quarter) AS quarter_count FROM {DB}.fact_sales"
    ),
    "fact_sales_no_negative_values": (
        f"SELECT count(*) AS invalid_rows FROM {DB}.fact_sales "
        "WHERE revenue < 0 OR profit < 0"
    ),
    "dim_customer": f"SELECT count(*) AS rows FROM {DB}.dim_customer",
    "dim_product": f"SELECT count(*) AS rows FROM {DB}.dim_product",
    "dim_date": f"SELECT count(*) AS rows FROM {DB}.dim_date",
    "dim_geography": f"SELECT count(*) AS rows FROM {DB}.dim_geography",
    "v_sales_by_product": (
        f"SELECT product_line, total_revenue FROM {DB}.sales_by_product "
        "ORDER BY total_revenue DESC LIMIT 3"
    ),
    "v_sales_by_quarter": (
        f"SELECT year_quarter, total_revenue FROM {DB}.sales_by_quarter "
        "ORDER BY year_quarter DESC LIMIT 3"
    ),
    "v_sales_by_loyalty": (
        f"SELECT loyaltystatus, loyalty_rank, total_revenue, unique_customers "
        f"FROM {DB}.sales_by_loyalty ORDER BY loyalty_rank"
    ),
    "v_customer_value": (
        f"SELECT customer_id, total_revenue FROM {DB}.customer_value "
        "ORDER BY total_revenue DESC LIMIT 3"
    ),
    "v_retention_priority": (
        f"SELECT retention_priority, count(*) AS customers FROM {DB}.retention_priority "
        "GROUP BY retention_priority ORDER BY customers DESC"
    ),
    "v_churn_priority": (
        f"SELECT retention_priority, count(*) AS customers FROM {DB}.churn_priority_customers "
        "GROUP BY retention_priority ORDER BY customers DESC"
    ),
}


def _run_query_once(client, query: str):
    response = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": config.ATHENA_DATABASE},
        ResultConfiguration={"OutputLocation": config.ATHENA_OUTPUT},
        WorkGroup=config.ATHENA_WORKGROUP,
    )
    query_id = response["QueryExecutionId"]
    start = time.time()
    while True:
        if time.time() - start > MAX_WAIT_SECONDS:
            raise TimeoutError(f"Query {query_id} exceeded {MAX_WAIT_SECONDS}s")
        status = client.get_query_execution(QueryExecutionId=query_id)["QueryExecution"]["Status"]
        state = status["State"]
        if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            if state != "SUCCEEDED":
                reason = status.get("StateChangeReason", "")
                raise RuntimeError(f"Athena {state}: {reason}")
            return client.get_query_results(QueryExecutionId=query_id)["ResultSet"]["Rows"]
        time.sleep(1)


def _run_query(client, query: str):
    for attempt in range(1, QUERY_ATTEMPTS + 1):
        try:
            return _run_query_once(client, query)
        except Exception:
            if attempt >= QUERY_ATTEMPTS:
                raise
            sleep_seconds = RETRY_BACKOFF_SECONDS * attempt
            print(f"      transient query error; retrying in {sleep_seconds}s...")
            time.sleep(sleep_seconds)


def main() -> None:
    client = boto3.client("athena")
    print(f"Validating Athena: {config.ATHENA_DATABASE} (workgroup: {config.ATHENA_WORKGROUP})")
    print()
    passed = 0
    for name, query in QUERIES.items():
        try:
            rows = _run_query(client, query)
            values = [
                " | ".join(cell.get("VarCharValue", "") for cell in row["Data"])
                for row in rows[1:]
            ]
            tag = "TABLE" if name.startswith("dim") or name == "fact_sales" else "VIEW"
            print(f"  OK {tag:<5} {name}")
            for value in values:
                print(f"      {value}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL {name}: {exc}")
    print()
    print(f"Validation complete: {passed}/{len(QUERIES)} checks passed")
    if passed != len(QUERIES):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
