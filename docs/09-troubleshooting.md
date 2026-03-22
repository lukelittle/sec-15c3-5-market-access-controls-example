# Troubleshooting Guide

Common issues and solutions for the streaming risk controls demo.

## Table of Contents
- [Deployment Issues](#deployment-issues)
- [Kafka Issues](#kafka-issues)
- [Lambda Issues](#lambda-issues)
- [Spark Issues](#spark-issues)
- [Networking Issues](#networking-issues)
- [Cost Issues](#cost-issues)

## Deployment Issues

### Terraform Init Fails

**Symptom**: `terraform init` fails with provider download errors

**Solutions**:
```bash
# Clear Terraform cache
rm -rf .terraform .terraform.lock.hcl

# Re-initialize
terraform init

# If behind proxy, set environment variables
export HTTP_PROXY=http://proxy:port
export HTTPS_PROXY=http://proxy:port
terraform init
```

### Terraform Apply Fails: MSK Cluster

**Symptom**: MSK cluster creation times out or fails

**Common causes**:
1. Insufficient subnet configuration
2. Wrong availability zones
3. IAM permissions missing

**Solutions**:
```bash
# Check subnet configuration
aws ec2 describe-subnets --subnet-ids <subnet-id>

# Verify subnets are in different AZs (if not low_cost_mode)
# Ensure subnets have available IP addresses

# Check IAM permissions
aws iam get-user
aws iam list-attached-user-policies --user-name <username>
```

### Terraform Apply Fails: Lambda

**Symptom**: Lambda function creation fails

**Common causes**:
1. Package not built
2. Package too large
3. IAM role not ready

**Solutions**:
```bash
# Rebuild Lambda packages
make build-lambdas

# Check package size (must be <50MB unzipped, <250MB zipped)
ls -lh services/*/dist/*.zip

# Wait for IAM role propagation (30-60 seconds)
sleep 60
terraform apply
```

## Kafka Issues

### Topics Not Created

**Symptom**: `create-topics.sh` fails or topics don't exist

**Solutions**:
```bash
# Check MSK cluster is ACTIVE
aws kafka describe-cluster --cluster-arn $MSK_CLUSTER_ARN

# Verify bootstrap brokers
echo $MSK_BOOTSTRAP

# Try creating topics manually
kafka-topics --bootstrap-server $MSK_BOOTSTRAP \
  --command-config /tmp/client.properties \
  --create --topic orders.v1 \
  --partitions 3 --replication-factor 1
```

### Can't Connect to Kafka

**Symptom**: Connection timeouts when accessing Kafka

**Common causes**:
1. Security group misconfiguration
2. Wrong bootstrap brokers
3. IAM authentication issues

**Solutions**:
```bash
# Verify security groups allow traffic
aws ec2 describe-security-groups --group-ids <msk-sg-id>

# Check Lambda is in VPC
aws lambda get-function-configuration \
  --function-name streaming-risk-dev-order-generator

# Test connectivity from Lambda
aws lambda invoke \
  --function-name streaming-risk-dev-order-generator \
  --payload '{"test": "connectivity"}' \
  response.json

# Check CloudWatch logs for connection errors
aws logs tail /aws/lambda/streaming-risk-dev-order-generator --follow
```

### Compaction Not Working

**Symptom**: Kill switch state topic not compacting

**Solutions**:
```bash
# Verify topic configuration
kafka-topics --bootstrap-server $MSK_BOOTSTRAP \
  --describe --topic killswitch.state.v1

# Should show: cleanup.policy=compact

# Check compaction settings
kafka-configs --bootstrap-server $MSK_BOOTSTRAP \
  --describe --topic killswitch.state.v1

# Force compaction (not available in MSK Serverless)
# Wait for natural compaction cycle (based on segment.ms)
```

## Lambda Issues

### Lambda Timeout

**Symptom**: Lambda function times out after 15 minutes

**Solutions**:
```bash
# Check Lambda timeout setting
aws lambda get-function-configuration \
  --function-name streaming-risk-dev-order-generator

# Reduce duration in payload
aws lambda invoke \
  --function-name streaming-risk-dev-order-generator \
  --payload '{"mode": "normal", "duration_seconds": 600}' \
  response.json

# For continuous processing, use EventBridge scheduled invocations
```

### Lambda Out of Memory

**Symptom**: Lambda fails with "out of memory" error

**Solutions**:
```bash
# Increase memory in Terraform
# In terraform/modules/lambdas/main.tf:
resource "aws_lambda_function" "order_router" {
  memory_size = 2048  # Increase from 1024
}

# Apply changes
terraform apply

# Monitor memory usage
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name MemoryUtilization \
  --dimensions Name=FunctionName,Value=streaming-risk-dev-order-router \
  --start-time 2024-03-15T00:00:00Z \
  --end-time 2024-03-15T23:59:59Z \
  --period 300 \
  --statistics Average
```

### Lambda Can't Write to DynamoDB

**Symptom**: DynamoDB write errors in Lambda logs

**Solutions**:
```bash
# Check IAM permissions
aws iam get-role-policy \
  --role-name streaming-risk-dev-order-router-role \
  --policy-name order-router-policy

# Verify table exists
aws dynamodb describe-table \
  --table-name streaming-risk-dev-audit-index

# Check VPC endpoint for DynamoDB
aws ec2 describe-vpc-endpoints --filters Name=service-name,Values=com.amazonaws.us-east-1.dynamodb
```

## Spark Issues

### Spark Job Won't Start

**Symptom**: EMR job run fails immediately

**Common causes**:
1. S3 permissions
2. Spark job not uploaded
3. Wrong bootstrap brokers

**Solutions**:
```bash
# Verify Spark job is in S3
aws s3 ls s3://$S3_BUCKET/spark-jobs/

# Check EMR execution role permissions
aws iam get-role-policy \
  --role-name streaming-risk-dev-emr-exec-role \
  --policy-name emr-execution-policy

# Check job run status
aws emr-serverless get-job-run \
  --application-id $EMR_APP_ID \
  --job-run-id <job-run-id>

# View detailed logs
aws s3 cp s3://$S3_BUCKET/spark-logs/$EMR_APP_ID/jobs/<job-run-id>/SPARK_DRIVER/stderr.gz - | gunzip
```

### Spark Job Crashes

**Symptom**: Job runs but crashes during execution

**Solutions**:
```bash
# Check Spark logs
aws s3 ls s3://$S3_BUCKET/spark-logs/$EMR_APP_ID/jobs/<job-run-id>/

# Download and view stderr
aws s3 cp s3://$S3_BUCKET/spark-logs/$EMR_APP_ID/jobs/<job-run-id>/SPARK_DRIVER/stderr.gz - | gunzip | less

# Common issues:
# 1. Kafka connection timeout - check security groups
# 2. Out of memory - increase executor memory
# 3. Missing dependencies - check spark.jars.packages
```

### Spark Not Emitting Signals

**Symptom**: No messages in risk_signals.v1 topic

**Solutions**:
```bash
# Check if Spark job is running
aws emr-serverless list-job-runs --application-id $EMR_APP_ID

# Verify orders are flowing
./tools/tail-topic.sh orders.v1

# Check Spark console output
aws s3 cp s3://$S3_BUCKET/spark-logs/$EMR_APP_ID/jobs/<job-run-id>/SPARK_DRIVER/stdout.gz - | gunzip

# Verify Spark can read from Kafka
# Look for "Starting streaming query" in logs
```

## Networking Issues

### VPC Endpoint Not Working

**Symptom**: Lambda can't reach S3 or DynamoDB

**Solutions**:
```bash
# Check VPC endpoints exist
aws ec2 describe-vpc-endpoints --filters Name=vpc-id,Values=<vpc-id>

# Verify route table associations
aws ec2 describe-route-tables --filters Name=vpc-id,Values=<vpc-id>

# Check endpoint policy
aws ec2 describe-vpc-endpoints --vpc-endpoint-ids <endpoint-id>
```

### Security Group Issues

**Symptom**: Services can't communicate

**Solutions**:
```bash
# List security groups
aws ec2 describe-security-groups --filters Name=vpc-id,Values=<vpc-id>

# Check MSK security group allows Lambda
aws ec2 describe-security-groups --group-ids <msk-sg-id>

# Should have ingress rule:
# Port 9098, Source: Lambda security group

# Check Lambda security group allows outbound
aws ec2 describe-security-groups --group-ids <lambda-sg-id>

# Should have egress rule:
# All traffic, Destination: 0.0.0.0/0
```

## Cost Issues

### Unexpected High Costs

**Symptom**: AWS bill higher than expected

**Solutions**:
```bash
# Check current costs
aws ce get-cost-and-usage \
  --time-period Start=2024-03-01,End=2024-03-31 \
  --granularity DAILY \
  --metrics BlendedCost

# Identify expensive resources
aws ce get-cost-and-usage \
  --time-period Start=2024-03-01,End=2024-03-31 \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=SERVICE

# Check for orphaned resources
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Project,Values=sec-15c3-5-market-access-controls

# Destroy infrastructure
cd terraform/envs/dev
terraform destroy
```

### NAT Gateway Charges

**Symptom**: High data transfer costs

**Solutions**:
```bash
# Verify low_cost_mode is enabled
cd terraform/envs/dev
grep low_cost_mode variables.tf

# Should be: default = true

# Check for NAT gateways (should be none in low_cost_mode)
aws ec2 describe-nat-gateways --filter Name=vpc-id,Values=<vpc-id>

# If NAT gateway exists, delete it
aws ec2 delete-nat-gateway --nat-gateway-id <nat-gw-id>
```

## General Debugging

### Enable Debug Logging

**Lambda**:
```python
import logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
```

**Terraform**:
```bash
export TF_LOG=DEBUG
terraform apply
```

**AWS CLI**:
```bash
aws --debug <command>
```

### Check CloudWatch Logs

```bash
# Tail logs in real-time
aws logs tail /aws/lambda/streaming-risk-dev-order-generator --follow

# Search logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/streaming-risk-dev-order-generator \
  --filter-pattern "ERROR"

# Get recent errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/streaming-risk-dev-order-generator \
  --start-time $(date -u -d '1 hour ago' +%s)000 \
  --filter-pattern "ERROR"
```

### Verify Kafka Message Flow

```bash
# Check producer is sending
./tools/tail-topic.sh orders.v1

# Check consumer is reading
./tools/tail-topic.sh orders.gated.v1

# Check audit trail
./tools/tail-topic.sh audit.v1

# Count messages
kafka-run-class kafka.tools.GetOffsetShell \
  --broker-list $MSK_BOOTSTRAP \
  --topic orders.v1
```

### Test Individual Components

**Test order generator**:
```bash
aws lambda invoke \
  --function-name streaming-risk-dev-order-generator \
  --payload '{"mode": "normal", "duration_seconds": 10}' \
  response.json

cat response.json
```

**Test operator console**:
```bash
curl -X POST $API_URL/health
curl -X POST $API_URL/kill \
  -H "Content-Type: application/json" \
  -d '{"scope": "GLOBAL", "reason": "Test"}'
```

**Test DynamoDB**:
```bash
aws dynamodb scan \
  --table-name streaming-risk-dev-audit-index \
  --limit 10
```

## Getting More Help

If issues persist:

1. **Check CloudWatch Logs** for detailed error messages
2. **Review Terraform state**: `terraform show`
3. **Verify AWS service limits**: Check Service Quotas
4. **Search GitHub Issues**: Similar problems may be documented
5. **Open an Issue**: Provide logs, configuration, and steps to reproduce

## Common Error Messages

### "Unable to import module 'handler'"

**Cause**: Lambda package missing dependencies

**Solution**: Rebuild Lambda package
```bash
cd services/order_generator
./build.sh
```

### "Task timed out after 900.00 seconds"

**Cause**: Lambda timeout (15 min max)

**Solution**: Reduce duration or use EventBridge for longer runs

### "Rate exceeded"

**Cause**: AWS API rate limiting

**Solution**: Add exponential backoff, reduce request rate

### "Access Denied"

**Cause**: IAM permissions insufficient

**Solution**: Check IAM policies, verify resource ARNs

### "Network timeout"

**Cause**: Security group or VPC misconfiguration

**Solution**: Verify security groups, check VPC endpoints

## Prevention Tips

1. **Test locally first** with Docker Compose
2. **Deploy incrementally** (one module at a time)
3. **Monitor costs** with billing alerts
4. **Use low_cost_mode** for demos
5. **Destroy after use** to avoid charges
6. **Keep Terraform state** backed up
7. **Document changes** for reproducibility

## Still Stuck?

- Review [00-overview.md](00-overview.md) for architecture
- Check [02-deploy-aws.md](02-deploy-aws.md) for deployment steps
- Read [08-security-notes.md](08-security-notes.md) for security issues
- Open a GitHub Issue with:
  - Error message
  - CloudWatch logs
  - Terraform output
  - Steps to reproduce
