output "order_generator_function_name" {
  description = "Order generator function name"
  value       = aws_lambda_function.order_generator.function_name
}

output "order_generator_lambda_arn" {
  description = "Order generator Lambda ARN"
  value       = aws_lambda_function.order_generator.arn
}

output "killswitch_aggregator_lambda_arn" {
  description = "Kill switch aggregator Lambda ARN"
  value       = aws_lambda_function.killswitch_aggregator.arn
}

output "order_router_lambda_arn" {
  description = "Order router Lambda ARN"
  value       = aws_lambda_function.order_router.arn
}

output "operator_console_lambda_arn" {
  description = "Operator console Lambda ARN"
  value       = aws_lambda_function.operator_console.arn
}

output "operator_console_lambda_name" {
  description = "Operator console Lambda name"
  value       = aws_lambda_function.operator_console.function_name
}

output "order_generator_log_group" {
  description = "Order generator log group name"
  value       = aws_cloudwatch_log_group.order_generator.name
}

output "killswitch_aggregator_log_group" {
  description = "Kill switch aggregator log group name"
  value       = aws_cloudwatch_log_group.killswitch_aggregator.name
}

output "order_router_log_group" {
  description = "Order router log group name"
  value       = aws_cloudwatch_log_group.order_router.name
}

output "operator_console_log_group" {
  description = "Operator console log group name"
  value       = aws_cloudwatch_log_group.operator_console.name
}
