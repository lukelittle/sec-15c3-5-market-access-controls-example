output "application_id" {
  description = "EMR Serverless application ID"
  value       = aws_emrserverless_application.spark.id
}

output "application_arn" {
  description = "EMR Serverless application ARN"
  value       = aws_emrserverless_application.spark.arn
}

output "execution_role_arn" {
  description = "EMR execution role ARN (passed through)"
  value       = var.execution_role_arn
}
