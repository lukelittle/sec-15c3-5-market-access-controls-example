output "msk_bootstrap_brokers" {
  description = "MSK Serverless bootstrap brokers (IAM auth)"
  value       = module.msk.bootstrap_brokers
}

output "msk_cluster_arn" {
  description = "MSK cluster ARN"
  value       = module.msk.cluster_arn
}

output "operator_console_url" {
  description = "API Gateway URL for operator console"
  value       = module.api_gateway.api_endpoint
}

output "s3_bucket_name" {
  description = "S3 bucket for artifacts"
  value       = module.s3.bucket_name
}

output "emr_application_id" {
  description = "EMR Serverless application ID"
  value       = module.emr_serverless.application_id
}

output "emr_execution_role_arn" {
  description = "EMR execution role ARN"
  value       = module.emr_serverless.execution_role_arn
}

output "order_generator_function_name" {
  description = "Order generator Lambda function name"
  value       = module.lambdas.order_generator_function_name
}

output "dynamodb_audit_table" {
  description = "DynamoDB audit index table name"
  value       = module.dynamodb.audit_table_name
}

output "cloudwatch_dashboard_url" {
  description = "CloudWatch dashboard URL"
  value       = "https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${module.cloudwatch.dashboard_name}"
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnet_ids
}
