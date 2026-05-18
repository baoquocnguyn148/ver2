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


STATEMENTS = [
    f"DROP VIEW IF EXISTS {DB}.sales_by_product",
    f"""
    CREATE VIEW {DB}.sales_by_product AS
    SELECT
      p.product_line,
      count(*) AS transaction_rows,
      sum(f.order_count) AS total_orders,
      sum(f.quantity_sold) AS total_quantity,
      round(sum(f.revenue), 2) AS total_revenue,
      round(sum(f.profit), 2) AS total_profit,
      round(sum(f.profit) / nullif(sum(f.revenue), 0) * 100, 2) AS profit_margin_pct
    FROM {DB}.fact_sales f
    LEFT JOIN {DB}.dim_product p
      ON f.product_id = p.product_id
    GROUP BY p.product_line
    """,
    f"DROP VIEW IF EXISTS {DB}.sales_by_quarter",
    f"""
    CREATE VIEW {DB}.sales_by_quarter AS
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
    FROM {DB}.fact_sales
    GROUP BY year, quarter, quarter_num, year_quarter
    """,
    f"DROP VIEW IF EXISTS {DB}.sales_by_loyalty",
    f"""
    CREATE VIEW {DB}.sales_by_loyalty AS
    SELECT
      f.loyaltystatus,
      f.loyalty_rank,
      count(DISTINCT f.customer_id) AS unique_customers,
      count(*) AS transaction_rows,
      round(sum(f.revenue), 2) AS total_revenue,
      round(sum(f.profit), 2) AS total_profit,
      round(avg(c.clv), 2) AS avg_clv,
      round(sum(f.revenue) / nullif(count(DISTINCT f.customer_id), 0), 2) AS revenue_per_customer
    FROM {DB}.fact_sales f
    LEFT JOIN {DB}.dim_customer c
      ON f.customer_id = c.customer_id
    GROUP BY f.loyaltystatus, f.loyalty_rank
    """,
    f"DROP VIEW IF EXISTS {DB}.churn_priority_customers",
    f"""
    CREATE VIEW {DB}.churn_priority_customers AS
    WITH customer_sales AS (
      SELECT
        customer_id,
        sum(order_count) AS total_orders,
        round(sum(revenue), 2) AS total_revenue,
        round(sum(profit), 2) AS total_profit,
        max(year_quarter) AS last_observed_quarter,
        max(quarter_idx) AS last_quarter_idx
      FROM {DB}.fact_sales
      GROUP BY customer_id
    ),
    max_period AS (
      SELECT max(quarter_idx) AS max_quarter_idx
      FROM {DB}.fact_sales
    )
    SELECT
      c.customer_id,
      c.full_name,
      c.loyaltystatus,
      c.loyalty_rank,
      c.clv,
      c.clv_segment,
      c.months_as_member,
      s.total_orders,
      s.total_revenue,
      s.total_profit,
      s.last_observed_quarter,
      (m.max_quarter_idx - s.last_quarter_idx) AS quarters_since_last_purchase,
      CASE
        WHEN (m.max_quarter_idx - s.last_quarter_idx) >= 8
          OR (c.clv_segment = 'Top CLV' AND s.total_revenue >= 5000) THEN 'Critical'
        WHEN (m.max_quarter_idx - s.last_quarter_idx) >= 4
          OR c.clv_segment IN ('Top CLV', 'High CLV') THEN 'High Risk'
        WHEN (m.max_quarter_idx - s.last_quarter_idx) >= 2
          OR s.total_revenue >= 3000 THEN 'Medium Risk'
        WHEN s.total_revenue > 0 THEN 'Low Risk'
        ELSE 'Monitor'
      END AS retention_priority
    FROM {DB}.dim_customer c
    LEFT JOIN customer_sales s ON c.customer_id = s.customer_id
    CROSS JOIN max_period m
    """,
]


def main() -> None:
    client = boto3.client("athena")
    print(f"Creating Athena demo views in: {config.ATHENA_DATABASE} (workgroup: {config.ATHENA_WORKGROUP})")
    for statement in STATEMENTS:
        label = statement.strip().splitlines()[0][:80]
        query_id = _run_query(client, statement)
        print(f"  OK: {label} ({query_id})")


if __name__ == "__main__":
    main()
