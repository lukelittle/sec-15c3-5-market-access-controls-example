variable "environment" {
  description = "Environment name"
  type        = string
}

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "msk_cluster_arn" {
  description = "MSK cluster ARN"
  type        = string
}

variable "s3_bucket_arn" {
  description = "S3 bucket ARN"
  type        = string
}

variable "dynamodb_table_arns" {
  description = "DynamoDB table ARNs"
  type        = list(string)
}
