CREATE VIEW {db}.sales_by_quarter AS
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
FROM {db}.fact_sales
GROUP BY year, quarter, quarter_num, year_quarter

