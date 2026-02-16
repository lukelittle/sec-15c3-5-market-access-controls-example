variable "environment" {
  description = "Environment name"
  type        = string
}

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs"
  type        = list(string)
}

variable "msk_bootstrap_brokers" {
  description = "MSK bootstrap brokers"
  type        = string
}

variable "dynamodb_audit_table" {
  description = "DynamoDB audit table name"
  type        = string
}

variable "dynamodb_state_table" {
  description = "DynamoDB state table name"
  type        = string
}

variable "order_generator_role_arn" {
  description = "Order generator Lambda role ARN"
  type        = string
}

variable "killswitch_aggregator_role_arn" {
  description = "Kill switch aggregator Lambda role ARN"
  type        = string
}

variable "order_router_role_arn" {
  description = "Order router Lambda role ARN"
  type        = string
}

variable "operator_console_role_arn" {
  description = "Operator console Lambda role ARN"
  type        = string
}
