from __future__ import annotations

import sys
import time
from pathlib import Path

import boto3

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import config


STATEMENTS = [
    "DROP VIEW IF EXISTS retail_analytics.sales_by_product",
    """
    CREATE VIEW retail_analytics.sales_by_product AS
    SELECT
      p.product_line,
      count(*) AS transaction_rows,
      sum(f.order_count) AS total_orders,
      sum(f.quantity_sold) AS total_quantity,
      round(sum(f.revenue), 2) AS total_revenue,
      round(sum(f.profit), 2) AS total_profit,
      round(sum(f.profit) / nullif(sum(f.revenue), 0) * 100, 2) AS profit_margin_pct
    FROM retail_analytics.fact_sales f
    LEFT JOIN retail_analytics.dim_product p
      ON f.product_id = p.product_id
    GROUP BY p.product_line
    """,
    "DROP VIEW IF EXISTS retail_analytics.sales_by_quarter",
    """
    CREATE VIEW retail_analytics.sales_by_quarter AS
    SELECT
      year,
      quarter,
      quarter_num,
      year_quarter,
      count(*) AS transaction_rows,
      sum(order_count) AS total_orders,
      round(sum(revenue), 2) AS total_revenue,
      round(sum(profit), 2) AS total_profit,
      round(sum(profit) / nullif(sum(revenue), 0) * 100, 2) AS profit_margin_pct
    FROM retail_analytics.fact_sales
    GROUP BY year, quarter, quarter_num, year_quarter
    """,
    "DROP VIEW IF EXISTS retail_analytics.churn_priority_customers",
    """
    CREATE VIEW retail_analytics.churn_priority_customers AS
    WITH customer_sales AS (
      SELECT
        customer_id,
        sum(order_count) AS total_orders,
        round(sum(revenue), 2) AS total_revenue,
        round(sum(profit), 2) AS total_profit,
        max(year_quarter) AS last_observed_quarter
      FROM retail_analytics.fact_sales
      GROUP BY customer_id
    )
    SELECT
      c.customer_id,
      c.full_name,
      c.loyaltystatus,
      c.clv,
      c.clv_segment,
      c.months_as_member,
      s.total_orders,
      s.total_revenue,
      s.total_profit,
      s.last_observed_quarter,
      CASE
        WHEN c.clv_segment = 'Top CLV' AND s.total_revenue >= 5000 THEN 'Critical'
        WHEN c.clv_segment IN ('Top CLV', 'High CLV') THEN 'High Risk'
        WHEN s.total_revenue >= 3000 THEN 'Medium Risk'
        ELSE 'Monitor'
      END AS retention_priority
    FROM retail_analytics.dim_customer c
    LEFT JOIN customer_sales s
      ON c.customer_id = s.customer_id
    """,
]


def _run_query(client, statement: str) -> str:
    response = client.start_query_execution(
        QueryString=statement,
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
            return query_id
        time.sleep(1)


def main() -> None:
    client = boto3.client("athena")
    print(f"Creating Athena demo views in database: {config.ATHENA_DATABASE}")
    for statement in STATEMENTS:
        query_id = _run_query(client, statement)
        print(f"  OK: {statement.strip().splitlines()[0]} ({query_id})")


if __name__ == "__main__":
    main()
