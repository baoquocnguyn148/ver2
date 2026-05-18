output "bucket_name" {
  value = aws_s3_bucket.data_lake.bucket
}

output "glue_database_name" {
  value = aws_glue_catalog_database.retail_analytics.name
}

output "athena_workgroup_name" {
  value = aws_athena_workgroup.retail_analytics.name
}

output "athena_output" {
  value = local.athena_output
}
