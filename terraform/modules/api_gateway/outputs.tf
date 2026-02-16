output "api_endpoint" {
  description = "API Gateway endpoint URL"
  value       = aws_apigatewayv2_api.operator_console.api_endpoint
}

output "api_id" {
  description = "API Gateway ID"
  value       = aws_apigatewayv2_api.operator_console.id
}
