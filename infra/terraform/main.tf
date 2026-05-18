locals {
  curated_prefix = "curated"
  output_prefix  = "outputs"
  athena_output  = "s3://${var.bucket_name}/${local.output_prefix}/athena/"
}

resource "aws_s3_bucket" "data_lake" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_public_access_block" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_glue_catalog_database" "retail_analytics" {
  name = var.glue_database_name
}

resource "aws_athena_workgroup" "retail_analytics" {
  name = "${var.glue_database_name}_workgroup"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = local.athena_output
    }
  }
}

resource "aws_iam_policy" "pipeline_policy" {
  name        = "ver2-retail-pipeline-policy"
  description = "Least-privilege policy for the retail analytics portfolio pipeline."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "S3BucketAccess"
        Effect   = "Allow"
        Action   = ["s3:GetBucketLocation", "s3:ListBucket"]
        Resource = aws_s3_bucket.data_lake.arn
      },
      {
        Sid    = "S3ObjectAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "${aws_s3_bucket.data_lake.arn}/*"
      },
      {
        Sid    = "GlueCatalogAccess"
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetDatabases",
          "glue:GetTable",
          "glue:GetTables",
          "glue:GetPartition",
          "glue:GetPartitions",
          "glue:CreateDatabase",
          "glue:CreateTable",
          "glue:UpdateTable",
          "glue:DeleteTable",
          "glue:BatchCreatePartition",
          "glue:CreatePartition",
          "glue:UpdatePartition"
        ]
        Resource = "*"
      },
      {
        Sid    = "AthenaAccess"
        Effect = "Allow"
        Action = [
          "athena:StartQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
          "athena:GetWorkGroup",
          "athena:ListQueryExecutions",
          "athena:ListWorkGroups",
          "athena:StopQueryExecution"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_user_policy_attachment" "pipeline_user" {
  user       = var.pipeline_user_name
  policy_arn = aws_iam_policy.pipeline_policy.arn
}
