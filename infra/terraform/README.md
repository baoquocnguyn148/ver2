# Terraform Notes

This Terraform folder is the IaC version of the resources created manually for
the portfolio demo.

The S3 bucket, Glue database, and IAM user already exist in the current AWS
account, so import them before applying:

```powershell
terraform init
terraform import aws_s3_bucket.data_lake ver2-retail-analytics
terraform import aws_glue_catalog_database.retail_analytics 108875909547:retail_analytics
terraform import aws_iam_user_policy_attachment.pipeline_user ver2-de-user/arn:aws:iam::108875909547:policy/ver2-retail-pipeline-policy
terraform plan
```

If the policy attachment import fails because the policy does not exist yet,
run `terraform plan` and apply only after replacing the temporary
`AdministratorAccess` permission on `ver2-de-user`.

Do not run `terraform apply` blindly against already-created manual resources.
