# Remote backend configuration for Terraform state management.
#
# USAGE:
#   For a personal/portfolio project, the local backend (default) is fine.
#   To use S3 as a remote backend (recommended for team/CI use), uncomment
#   the block below and replace placeholders with your values, then run:
#     terraform init -reconfigure
#
# terraform {
#   backend "s3" {
#     bucket         = "ver2-retail-analytics"
#     key            = "infra/terraform.tfstate"
#     region         = "ap-southeast-2"
#     encrypt        = true
#     dynamodb_table = "terraform-lock"   # optional, prevents concurrent applies
#   }
# }
