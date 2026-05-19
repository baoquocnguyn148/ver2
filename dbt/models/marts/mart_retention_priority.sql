with customer_value as (
  select * from {{ ref('mart_customer_value') }}
),
max_period as (
  select max((year * 4) + quarter_num) as max_quarter_idx
  from {{ source('retail_analytics', 'fact_sales') }}
)
select
  cv.customer_id,
  cv.full_name,
  cv.loyaltystatus,
  cv.loyalty_rank,
  cv.clv,
  cv.clv_segment,
  cv.months_as_member,
  cv.total_orders,
  cv.total_revenue,
  cv.total_profit,
  cv.last_observed_quarter,
  (m.max_quarter_idx - cv.last_quarter_idx) as quarters_since_last_purchase,
  case
    when (m.max_quarter_idx - cv.last_quarter_idx) >= 8
      or (cv.clv_segment = 'Top CLV' and cv.total_revenue >= 5000) then 'Critical'
    when (m.max_quarter_idx - cv.last_quarter_idx) >= 4
      or cv.clv_segment in ('Top CLV', 'High CLV') then 'High Risk'
    when (m.max_quarter_idx - cv.last_quarter_idx) >= 2
      or cv.total_revenue >= 3000 then 'Medium Risk'
    when cv.total_revenue > 0 then 'Low Risk'
    else 'Monitor'
  end as retention_priority
from customer_value cv
cross join max_period m

