select
  year,
  quarter,
  quarter_num,
  year_quarter,
  count(*) as transaction_rows,
  sum(order_count) as total_orders,
  round(sum(revenue), 2) as total_revenue,
  round(sum(profit), 2) as total_profit,
  round(sum(profit) / nullif(sum(revenue), 0) * 100, 2) as profit_margin_pct
from {{ source('retail_analytics', 'fact_sales') }}
group by year, quarter, quarter_num, year_quarter

