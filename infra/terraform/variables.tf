variable "aws_region" {
  description = "AWS region that contains the S3 bucket, Glue database, and Athena workgroup."
  type        = string
  default     = "ap-southeast-2"
}

variable "bucket_name" {
  description = "Retail analytics data lake bucket."
  type        = string
  default     = "ver2-retail-analytics"
}

variable "glue_database_name" {
  description = "Glue catalog database for curated retail analytics tables."
  type        = string
  default     = "retail_analytics"
}

variable "pipeline_user_name" {
  description = "IAM user used by local/GitHub Actions pipeline credentials."
  type        = string
  default     = "ver2-de-user"
}
