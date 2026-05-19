select
  c.customer_id,
  c.full_name,
  c.loyaltystatus,
  c.loyalty_rank,
  c.clv,
  c.clv_segment,
  c.months_as_member,
  count(f.fact_id) as transaction_rows,
  coalesce(sum(f.order_count), 0) as total_orders,
  round(coalesce(sum(f.revenue), 0), 2) as total_revenue,
  round(coalesce(sum(f.profit), 0), 2) as total_profit,
  max(f.year_quarter) as last_observed_quarter,
  max((f.year * 4) + f.quarter_num) as last_quarter_idx
from {{ source('retail_analytics', 'dim_customer') }} c
left join {{ source('retail_analytics', 'fact_sales') }} f
  on c.customer_id = f.customer_id
group by
  c.customer_id,
  c.full_name,
  c.loyaltystatus,
  c.loyalty_rank,
  c.clv,
  c.clv_segment,
  c.months_as_member

