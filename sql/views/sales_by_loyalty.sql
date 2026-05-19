CREATE VIEW {db}.sales_by_loyalty AS
SELECT
  f.loyaltystatus,
  f.loyalty_rank,
  count(DISTINCT f.customer_id) AS unique_customers,
  count(*) AS transaction_rows,
  round(sum(f.revenue), 2) AS total_revenue,
  round(sum(f.profit), 2) AS total_profit,
  round(avg(c.clv), 2) AS avg_clv,
  round(sum(f.revenue) / nullif(count(DISTINCT f.customer_id), 0), 2) AS revenue_per_customer
FROM {db}.fact_sales f
LEFT JOIN {db}.dim_customer c
  ON f.customer_id = c.customer_id
GROUP BY f.loyaltystatus, f.loyalty_rank

