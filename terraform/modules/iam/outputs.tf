output "order_generator_role_arn" {
  description = "Order generator Lambda role ARN"
  value       = aws_iam_role.order_generator.arn
}

output "killswitch_aggregator_role_arn" {
  description = "Kill switch aggregator Lambda role ARN"
  value       = aws_iam_role.killswitch_aggregator.arn
}

output "order_router_role_arn" {
  description = "Order router Lambda role ARN"
  value       = aws_iam_role.order_router.arn
}

output "operator_console_role_arn" {
  description = "Operator console Lambda role ARN"
  value       = aws_iam_role.operator_console.arn
}

output "emr_execution_role_arn" {
  description = "EMR execution role ARN"
  value       = aws_iam_role.emr_execution.arn
}
