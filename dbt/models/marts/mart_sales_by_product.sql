select
  p.product_line,
  count(*) as transaction_rows,
  sum(f.order_count) as total_orders,
  sum(f.quantity_sold) as total_quantity,
  round(sum(f.revenue), 2) as total_revenue,
  round(sum(f.profit), 2) as total_profit,
  round(sum(f.profit) / nullif(sum(f.revenue), 0) * 100, 2) as profit_margin_pct
from {{ source('retail_analytics', 'fact_sales') }} f
left join {{ source('retail_analytics', 'dim_product') }} p
  on f.product_id = p.product_id
group by p.product_line

