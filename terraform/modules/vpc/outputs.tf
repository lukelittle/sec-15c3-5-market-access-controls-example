output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = aws_subnet.private[*].id
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = aws_subnet.public[*].id
}

output "msk_security_group_id" {
  description = "Security group ID for MSK"
  value       = aws_security_group.msk.id
}

output "lambda_security_group_id" {
  description = "Security group ID for Lambda functions"
  value       = aws_security_group.lambda.id
}
