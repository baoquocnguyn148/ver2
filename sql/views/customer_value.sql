CREATE VIEW {db}.customer_value AS
SELECT
  c.customer_id,
  c.full_name,
  c.loyaltystatus,
  c.loyalty_rank,
  c.clv,
  c.clv_segment,
  c.months_as_member,
  count(f.fact_id) AS transaction_rows,
  coalesce(sum(f.order_count), 0) AS total_orders,
  round(coalesce(sum(f.revenue), 0), 2) AS total_revenue,
  round(coalesce(sum(f.profit), 0), 2) AS total_profit,
  max(f.year_quarter) AS last_observed_quarter,
  max((f.year * 4) + f.quarter_num) AS last_quarter_idx
FROM {db}.dim_customer c
LEFT JOIN {db}.fact_sales f
  ON c.customer_id = f.customer_id
GROUP BY
  c.customer_id,
  c.full_name,
  c.loyaltystatus,
  c.loyalty_rank,
  c.clv,
  c.clv_segment,
  c.months_as_member
