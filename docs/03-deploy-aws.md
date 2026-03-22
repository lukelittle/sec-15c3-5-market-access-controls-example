# AWS Deployment Guide

## Overview

This guide walks through deploying the complete streaming risk controls demo to AWS using Terraform.

**Estimated time**: 20-30 minutes  
**Estimated cost**: $4-6 per hour of runtime

## Pre-Deployment Checklist

- [ ] AWS CLI configured (`aws sts get-caller-identity`)
- [ ] Terraform installed (`terraform version`)
- [ ] Python 3.11+ installed
- [ ] Docker running (for Lambda packaging)
- [ ] Reviewed [cost estimates](01-prereqs.md#cost-considerations)

## Step 1: Build Lambda Packages

Lambda functions need to be packaged with their dependencies before deployment.

```bash
# From repository root
make build-lambdas
```

This will:
- Install Python dependencies for each Lambda
- Package code and dependencies into zip files
- Place packages in `services/*/dist/`

**Expected output**:
```
Building Lambda packages...
✓ order_generator packaged
✓ killswitch_aggregator packaged
✓ order_router packaged
✓ operator_console packaged
```

## Step 2: Initialize Terraform

```bash
cd terraform/envs/dev
terraform init
```

This downloads required Terraform providers (AWS, local).

## Step 3: Review Configuration

Edit `terraform/envs/dev/variables.tf` if you want to customize:

```hcl
variable "aws_region" {
  default = "us-east-1"  # Change if needed
}

variable "low_cost_mode" {
  default = true  # Single AZ, no NAT gateway
}

variable "order_rate_threshold_60s" {
  default = 100  # Adjust risk thresholds
}
```

## Step 4: Plan Deployment

Review what Terraform will create:

```bash
terraform plan
```

**Expected resources** (~40-50 resources):
- 1 VPC with subnets, security groups, VPC endpoints
- 1 MSK Serverless cluster
- 4 Lambda functions
- 2 DynamoDB tables
- 1 S3 bucket
- 1 EMR Serverless application
- 1 API Gateway HTTP API
- IAM roles and policies
- CloudWatch log groups and dashboard

## Step 5: Deploy Infrastructure

```bash
terraform apply
```

Type `yes` when prompted.

**Deployment time**: 15-20 minutes (MSK cluster takes longest)

**Watch for**:
- MSK cluster creation (10-15 minutes)
- Lambda functions deploying
- EMR application starting

## Step 6: Capture Outputs

After deployment completes, save important outputs:

```bash
# MSK bootstrap brokers
export MSK_BOOTSTRAP=$(terraform output -raw msk_bootstrap_brokers)
echo $MSK_BOOTSTRAP

# Operator console API URL
export API_URL=$(terraform output -raw operator_console_url)
echo $API_URL

# EMR application ID
export EMR_APP_ID=$(terraform output -raw emr_application_id)
echo $EMR_APP_ID

# S3 bucket
export S3_BUCKET=$(terraform output -raw s3_bucket_name)
echo $S3_BUCKET
```

## Step 7: Create Kafka Topics

Topics must be created after MSK cluster is ready:

```bash
cd ../../../  # Back to repo root
./tools/create-topics.sh
```

This creates:
- `orders.v1` (regular topic)
- `risk_signals.v1` (regular topic)
- `killswitch.commands.v1` (regular topic)
- `killswitch.state.v1` (compacted topic)
- `orders.gated.v1` (regular topic)
- `audit.v1` (regular topic)

**Verify topics**:
```bash
kafka-topics --bootstrap-server $MSK_BOOTSTRAP \
  --command-config /tmp/client.properties \
  --list
```

## Step 8: Deploy Spark Job

Upload the Spark job to S3 and start it:

```bash
# Upload Spark job
aws s3 cp spark/risk_job/risk_detector.py \
  s3://$S3_BUCKET/spark-jobs/risk_detector.py

# Start Spark job (generated script)
./tools/run-spark-job.sh
```

**Monitor Spark job**:
```bash
# Get job run ID from output, then:
aws emr-serverless get-job-run \
  --application-id $EMR_APP_ID \
  --job-run-id <JOB_RUN_ID>
```

## Step 9: Start Lambda Functions

Lambdas are deployed but not running yet. Invoke them:

```bash
# Start order generator (normal mode)
aws lambda invoke \
  --function-name $(terraform output -raw order_generator_function_name) \
  --payload '{"mode": "normal", "duration_seconds": 300}' \
  response.json

# Start kill switch aggregator (runs continuously)
aws lambda invoke \
  --function-name streaming-risk-dev-killswitch-aggregator \
  --invocation-type Event \
  --payload '{}' \
  response.json

# Start order router (runs continuously)
aws lambda invoke \
  --function-name streaming-risk-dev-order-router \
  --invocation-type Event \
  --payload '{}' \
  response.json
```

## Step 10: Verify System is Running

Check that orders are flowing:

```bash
# Tail orders topic
./tools/tail-topic.sh orders.v1

# Check risk signals
./tools/tail-topic.sh risk_signals.v1

# Check CloudWatch logs
aws logs tail /aws/lambda/streaming-risk-dev-order-generator --follow
```

## Deployment Complete!

Your streaming risk control system is now running on AWS.

**Next steps**:
- [03-run-demo.md](03-run-demo.md): Run the live demo
- [04-observe.md](04-observe.md): Observability and monitoring
- [CloudWatch Dashboard](https://console.aws.amazon.com/cloudwatch/home#dashboards:): View metrics

## Troubleshooting

### MSK Cluster Creation Fails

**Symptom**: Terraform times out waiting for MSK cluster

**Solutions**:
- Check VPC subnet configuration
- Ensure subnets are in different AZs (if not low_cost_mode)
- Verify IAM permissions for MSK

### Lambda Functions Can't Connect to MSK

**Symptom**: Lambda logs show connection timeouts

**Solutions**:
- Verify Lambdas are in VPC private subnets
- Check security group allows traffic between Lambda and MSK
- Ensure MSK bootstrap brokers are correct

### Topics Not Created

**Symptom**: `create-topics.sh` fails

**Solutions**:
- Verify MSK cluster is fully ready (check AWS console)
- Check IAM authentication is configured
- Try creating topics manually via AWS console

### Spark Job Fails to Start

**Symptom**: EMR job run fails immediately

**Solutions**:
- Check S3 bucket permissions
- Verify EMR execution role has correct policies
- Check Spark job was uploaded to S3
- Review EMR logs in S3

### High Costs

**Symptom**: AWS bill higher than expected

**Solutions**:
- Ensure `low_cost_mode = true` in Terraform
- Destroy infrastructure when not in use: `terraform destroy`
- Check for orphaned resources: NAT gateways, EIPs
- Set up billing alerts

## Clean Up

When done with the demo:

```bash
cd terraform/envs/dev

# Destroy all infrastructure
terraform destroy
```

Type `yes` when prompted.

**Verify cleanup**:
```bash
# Check for remaining resources
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Project,Values=sec-15c3-5-market-access-controls
```

**Expected result**: Empty list

## Cost Breakdown

For a 1-hour demo session:

| Service | Estimated Cost |
|---------|---------------|
| MSK Serverless | $2-3 |
| EMR Serverless | $1-2 |
| Lambda | $0.50 |
| DynamoDB | $0.10 |
| S3 | $0.10 |
| Data Transfer | $0.50 |
| **Total** | **$4-6** |

Costs scale with:
- Duration of demo
- Order generation rate
- Spark job runtime
- Data retention

## Next Steps

- [03-run-demo.md](03-run-demo.md): Run the demo script
- [05-exercises.md](05-exercises.md): Student exercises
- [07-cost-and-cleanup.md](07-cost-and-cleanup.md): Detailed cost management
