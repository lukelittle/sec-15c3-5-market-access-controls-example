output "cluster_arn" {
  description = "MSK cluster ARN"
  value       = aws_msk_serverless_cluster.main.arn
}

output "bootstrap_brokers" {
  description = "MSK bootstrap brokers (IAM auth)"
  value       = aws_msk_serverless_cluster.main.bootstrap_brokers_sasl_iam
}
