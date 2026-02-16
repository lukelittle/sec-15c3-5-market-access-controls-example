variable "environment" {
  description = "Environment name"
  type        = string
}

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "s3_bucket_arn" {
  description = "S3 bucket ARN"
  type        = string
}

variable "s3_bucket_name" {
  description = "S3 bucket name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs"
  type        = list(string)
}

variable "msk_bootstrap_brokers" {
  description = "MSK bootstrap brokers"
  type        = string
}

variable "execution_role_arn" {
  description = "EMR execution role ARN"
  type        = string
}

variable "order_rate_threshold_60s" {
  description = "Order rate threshold"
  type        = number
}

variable "notional_threshold_60s" {
  description = "Notional threshold"
  type        = number
}

variable "symbol_concentration_threshold" {
  description = "Symbol concentration threshold"
  type        = number
}
