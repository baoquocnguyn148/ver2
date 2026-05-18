from __future__ import annotations

import sys
import time
from pathlib import Path

import boto3

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import config


QUERIES = {
    "fact_sales": "SELECT count(*) FROM retail_analytics.fact_sales",
    "dim_customer": "SELECT count(*) FROM retail_analytics.dim_customer",
    "dim_product": "SELECT count(*) FROM retail_analytics.dim_product",
    "dim_date": "SELECT count(*) FROM retail_analytics.dim_date",
    "sales_by_product": (
        "SELECT product_line, total_revenue "
        "FROM retail_analytics.sales_by_product "
        "ORDER BY total_revenue DESC LIMIT 5"
    ),
}


def _run_query(client, query: str):
    response = client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": config.ATHENA_DATABASE},
        ResultConfiguration={"OutputLocation": config.ATHENA_OUTPUT},
    )
    query_id = response["QueryExecutionId"]
    while True:
        status = client.get_query_execution(QueryExecutionId=query_id)["QueryExecution"]["Status"]
        state = status["State"]
        if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            if state != "SUCCEEDED":
                reason = status.get("StateChangeReason", "")
                raise RuntimeError(f"Athena query {query_id} {state}: {reason}")
            return client.get_query_results(QueryExecutionId=query_id)["ResultSet"]["Rows"]
        time.sleep(1)


def main() -> None:
    client = boto3.client("athena")
    print(f"Validating Athena database: {config.ATHENA_DATABASE}")
    for name, query in QUERIES.items():
        rows = _run_query(client, query)
        values = [
            " | ".join(cell.get("VarCharValue", "") for cell in row["Data"])
            for row in rows[1:]
        ]
        print(f"[{name}]")
        for value in values:
            print(f"  {value}")


if __name__ == "__main__":
    main()
