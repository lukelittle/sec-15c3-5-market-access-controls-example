output "audit_table_name" {
  description = "Audit index table name"
  value       = aws_dynamodb_table.audit_index.name
}

output "audit_table_arn" {
  description = "Audit index table ARN"
  value       = aws_dynamodb_table.audit_index.arn
}

output "state_table_name" {
  description = "State cache table name"
  value       = aws_dynamodb_table.state_cache.name
}

output "state_table_arn" {
  description = "State cache table ARN"
  value       = aws_dynamodb_table.state_cache.arn
}

output "table_arns" {
  description = "All table ARNs"
  value = [
    aws_dynamodb_table.audit_index.arn,
    aws_dynamodb_table.state_cache.arn
  ]
}
