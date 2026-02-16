variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
  default     = "streaming-risk"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "low_cost_mode" {
  description = "Enable low-cost mode (single AZ, minimal capacity). WARNING: Reduces resiliency."
  type        = bool
  default     = true
}

# Risk Control Thresholds
variable "order_rate_threshold_60s" {
  description = "Maximum orders per 60-second window before triggering kill switch"
  type        = number
  default     = 100
}

variable "notional_threshold_60s" {
  description = "Maximum notional value (price * qty) in 60-second window before triggering kill switch"
  type        = number
  default     = 1000000
}

variable "symbol_concentration_threshold" {
  description = "Maximum percentage of orders for a single symbol (0.0-1.0) before alerting"
  type        = number
  default     = 0.7
}
