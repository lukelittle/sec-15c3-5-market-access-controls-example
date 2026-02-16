variable "environment" {
  description = "Environment name"
  type        = string
}

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "order_generator_log_group" {
  description = "Order generator log group name"
  type        = string
}

variable "killswitch_aggregator_log_group" {
  description = "Kill switch aggregator log group name"
  type        = string
}

variable "order_router_log_group" {
  description = "Order router log group name"
  type        = string
}

variable "operator_console_log_group" {
  description = "Operator console log group name"
  type        = string
}
