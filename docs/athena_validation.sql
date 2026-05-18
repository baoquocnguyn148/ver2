SELECT count(*) AS fact_rows FROM retail_analytics.fact_sales;
SELECT count(*) AS customer_rows FROM retail_analytics.dim_customer;
SELECT count(*) AS product_rows FROM retail_analytics.dim_product;
SELECT count(*) AS date_rows FROM retail_analytics.dim_date;
SELECT count(*) AS geography_rows FROM retail_analytics.dim_geography;

SELECT
  partition_year,
  count(*) AS rows
FROM retail_analytics.fact_sales
GROUP BY partition_year
ORDER BY partition_year;

SELECT
  product_line,
  total_revenue,
  total_profit
FROM retail_analytics.sales_by_product
ORDER BY total_revenue DESC;

SELECT
  loyaltystatus,
  loyalty_rank,
  unique_customers,
  total_revenue
FROM retail_analytics.sales_by_loyalty
ORDER BY loyalty_rank;

SELECT
  retention_priority,
  count(*) AS customers
FROM retail_analytics.churn_priority_customers
GROUP BY retention_priority
ORDER BY customers DESC;
