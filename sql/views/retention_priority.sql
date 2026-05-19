CREATE VIEW {db}.retention_priority AS
WITH max_period AS (
  SELECT max((year * 4) + quarter_num) AS max_quarter_idx
  FROM {db}.fact_sales
)
SELECT
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
  (m.max_quarter_idx - cv.last_quarter_idx) AS quarters_since_last_purchase,
  CASE
    WHEN (m.max_quarter_idx - cv.last_quarter_idx) >= 8
      OR (cv.clv_segment = 'Top CLV' AND cv.total_revenue >= 5000) THEN 'Critical'
    WHEN (m.max_quarter_idx - cv.last_quarter_idx) >= 4
      OR cv.clv_segment IN ('Top CLV', 'High CLV') THEN 'High Risk'
    WHEN (m.max_quarter_idx - cv.last_quarter_idx) >= 2
      OR cv.total_revenue >= 3000 THEN 'Medium Risk'
    WHEN cv.total_revenue > 0 THEN 'Low Risk'
    ELSE 'Monitor'
  END AS retention_priority
FROM {db}.customer_value cv
CROSS JOIN max_period m
