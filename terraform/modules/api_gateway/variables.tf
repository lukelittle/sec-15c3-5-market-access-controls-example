variable "environment" {
  description = "Environment name"
  type        = string
}

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "operator_console_lambda_arn" {
  description = "Operator console Lambda ARN"
  type        = string
}

variable "operator_console_lambda_name" {
  description = "Operator console Lambda name"
  type        = string
}
