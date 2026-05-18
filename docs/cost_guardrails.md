# Cost Guardrails

This project is designed to stay small and free-tier friendly.

## Required

- Create an AWS Budget before adding more scheduled services.
- Use region `ap-southeast-2` consistently for S3, Glue, and Athena.
- Query Athena only on curated Parquet tables.
- Keep raw Excel out of Athena query paths.
- Keep the Amplify site static.
- Remove `AdministratorAccess` from `ver2-de-user` after attaching
  `docs/iam_pipeline_policy.json`.

## Avoid For The Portfolio MVP

- QuickSight dashboards unless you explicitly accept the pricing.
- Glue ETL jobs or crawlers on a schedule.
- Frequent ECS/Fargate scheduled runs.
- Large ECR images with many retained versions.

## Recommended Budget

Current project budget:

```text
Name: ver2-retail-analytics-budget
Amount: 5 USD
```

Add an email notification in AWS Billing:

```text
Alert threshold: 80%
Email: your own email address
```

## Cleanup Checklist

If you pause the project:

- Disable GitHub Actions schedule.
- Delete old Athena query result files under `outputs/athena/` if they grow.
- Delete unused Amplify apps.
- Keep only the latest Docker/ECR image if ECR is added.
