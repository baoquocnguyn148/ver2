# Retail Sales Analytics Dashboard - AWS Data Lakehouse

End-to-end retail analytics project that turns raw Excel transaction data into
an AWS-ready data lakehouse, Athena query layer, Power BI dashboard portfolio,
and machine learning outputs for revenue/profit forecasting and churn
prioritization.

Public portfolio site:

https://main.dkb6koqkmw7iv.amplifyapp.com

## Project Highlights

| Area | Result |
|---|---:|
| Sales transactions | 84,436 |
| Unique customers | 63,228 |
| Time range | 2016-Q1 to 2020-Q1 |
| Total revenue | $228.74M |
| Total profit | $34.30M |
| Profit margin | 15.00% |
| Power BI dashboard pages | Sales, Product, Customer |
| ML outputs | Forecast, churn scores, model metrics, reports |

## Architecture

```text
GitHub / Local Runner / GitHub Actions
  -> Python pipeline
      -> read raw Excel from S3
      -> build star schema data model
      -> write curated Parquet to S3
      -> train forecast and churn models
      -> upload CSV, Excel, model, and image outputs to S3

S3 Data Lake
  raw/DB.xlsx
  curated/fact_sales/
  curated/dim_customer/
  curated/dim_product/
  curated/dim_date/
  outputs/

Glue Data Catalog
  -> external Parquet tables

Athena
  -> table validation queries
  -> demo views

Amplify Hosting
  -> static portfolio site
```

## AWS Validation

The cloud pipeline has been validated in AWS region `ap-southeast-2`.

| Athena table | Row count |
|---|---:|
| `fact_sales` | 84,436 |
| `dim_customer` | 63,228 |
| `dim_product` | 5 |
| `dim_date` | 17 |

Validated Athena views:

- `sales_by_product`
- `sales_by_quarter`
- `churn_priority_customers`

Top product revenue from Athena:

| Product line | Revenue |
|---|---:|
| TV and Video Gaming | 97,846,550 |
| Computers and Home Office | 85,660,668 |
| Photography | 24,264,200 |
| Kitchen Appliances | 15,885,783 |
| Smart Electronics | 5,084,355 |

## Repository Structure

| Path | Purpose |
|---|---|
| `data_process.py` | Builds the Power BI data model and curated Parquet tables. |
| `ml_pipeline.py` | Canonical entrypoint for forecasting and churn pipeline. |
| `src/` | Modular data loading, validation, feature engineering, models, training, and IO utilities. |
| `scripts/` | Cloud pipeline orchestration, Glue registration, Athena repair, views, and validation. |
| `docs/images/` | Power BI dashboard images and confusion matrix image. |
| `docs/aws_deployment.md` | AWS runbook and validation notes. |
| `infra/terraform/` | Terraform scaffold for S3, Glue, Athena, and IAM. |
| `.github/workflows/` | CI, cloud pipeline, and Docker build workflows. |
| `index.html` | Static Amplify portfolio page. |

## Cloud Module

The cloud module is the set of config, IO helpers, scripts, and workflows that
turn the original local Excel project into an AWS-ready pipeline.

| Component | Responsibility |
|---|---|
| `src/config.py` | Reads `.env` or environment variables for local/cloud mode. |
| `src/utils/io_utils.py` | Reads Excel from local/S3 and writes CSV, Excel, Parquet, and binary artifacts. |
| `scripts/run_cloud_pipeline.py` | Runs the full cloud pipeline end to end. |
| `scripts/register_glue_tables.py` | Recreates Glue external table metadata from the curated Parquet datasets. |
| `scripts/repair_athena_tables.py` | Runs `MSCK REPAIR TABLE` for partition discovery. |
| `scripts/create_athena_views.py` | Creates the Athena portfolio views. |
| `scripts/validate_athena.py` | Runs smoke queries against Athena and prints row counts/top products. |
| `.github/workflows/pipeline.yml` | Runs the cloud pipeline manually or on a weekly schedule. |

Cloud execution flow:

```text
S3 raw/DB.xlsx
  -> data_process.py
  -> S3 curated/*.parquet
  -> ml_pipeline.py
  -> S3 outputs/*
  -> Glue table registration
  -> Athena partition repair
  -> Athena demo views
  -> validation queries
```

## Data Lake Layout

```text
s3://ver2-retail-analytics/
  raw/
    DB.xlsx
  curated/
    fact_sales/partition_year=YYYY/*.parquet
    dim_customer/partition_loyalty_status=.../*.parquet
    dim_product/*.parquet
    dim_date/partition_year=YYYY/*.parquet
  outputs/
    forecast and churn CSVs
    reports/*.xlsx
    models/*.pkl
    images/confusion_matrix.png
    athena/
```

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m unittest discover -s tests
```

Local mode uses repo files:

```env
LOCAL_MODE=true
```

Cloud mode uses S3 and Athena:

```env
LOCAL_MODE=false
S3_BUCKET=ver2-retail-analytics
RAW_KEY=raw/DB.xlsx
CURATED_PREFIX=curated/
OUTPUT_PREFIX=outputs/
ATHENA_DATABASE=retail_analytics
ATHENA_OUTPUT=s3://ver2-retail-analytics/outputs/athena/
AWS_DEFAULT_REGION=ap-southeast-2
WORK_DIR=C:\tmp\ver2
```

## Run The Cloud Pipeline

Configure AWS credentials first. Do not commit `.env` or access keys.

```powershell
.\aws.cmd sts get-caller-identity
.\aws.cmd s3 ls s3://ver2-retail-analytics/raw/
```

Run the full cloud pipeline:

```powershell
$env:PYTHONIOENCODING="utf-8"
python scripts/run_cloud_pipeline.py
```

This runs:

1. `data_process.py`
2. `ml_pipeline.py`
3. `scripts/register_glue_tables.py`
4. `scripts/repair_athena_tables.py`
5. `scripts/create_athena_views.py`
6. `scripts/validate_athena.py`

## Dashboard Preview

![Sales dashboard](docs/images/sales_dashboard.png)

![Product dashboard](docs/images/product_dashboard.png)

![Customer dashboard](docs/images/customer_dashboard.png)

![Confusion matrix](docs/images/confusion_matrix.png)

## GitHub Actions

Required repository secrets:

```text
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
```

Workflows:

- `CI`: install dependencies and run tests.
- `Cloud Pipeline`: manual or weekly scheduled S3/Glue/Athena pipeline.
- `Docker Build`: verify that the container image builds.

## Docker

Build locally:

```powershell
docker build -t ver2-retail-analytics:latest .
```

Run with AWS credentials available in the environment:

```powershell
docker run --rm `
  -e AWS_ACCESS_KEY_ID `
  -e AWS_SECRET_ACCESS_KEY `
  -e AWS_DEFAULT_REGION=ap-southeast-2 `
  ver2-retail-analytics:latest
```

## Cost And Security Notes

- Use Athena against curated Parquet, not Excel.
- Avoid QuickSight unless the pricing/trial is intentional.
- Do not schedule Fargate for frequent runs.
- Keep ECR lifecycle to 1-2 images if ECR is added later.
- Replace temporary `AdministratorAccess` with the least-privilege policy in
  `docs/iam_pipeline_policy.json`.
- Create an AWS Budget before adding more scheduled services.

## Status

Completed:

- Local and S3-ready IO layer.
- S3 raw, curated, and outputs layers.
- Curated Parquet tables.
- Glue Data Catalog and Athena views.
- ML outputs uploaded to S3.
- Static Amplify portfolio.
- Dockerfile, GitHub Actions, Terraform scaffold, and AWS runbook.

Optional next step:

- EventBridge -> Step Functions -> Lambda container orchestration.
