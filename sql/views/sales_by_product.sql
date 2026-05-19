CREATE VIEW {db}.sales_by_product AS
SELECT
  p.product_line,
  count(*) AS transaction_rows,
  sum(f.order_count) AS total_orders,
  sum(f.quantity_sold) AS total_quantity,
  round(sum(f.revenue), 2) AS total_revenue,
  round(sum(f.profit), 2) AS total_profit,
  round(sum(f.profit) / nullif(sum(f.revenue), 0) * 100, 2) AS profit_margin_pct
FROM {db}.fact_sales f
LEFT JOIN {db}.dim_product p
  ON f.product_id = p.product_id
GROUP BY p.product_line

