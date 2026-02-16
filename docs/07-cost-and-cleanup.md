# Cost Management and Cleanup

## Cost Breakdown

### Per-Hour Costs (Typical Demo)

| Service | Configuration | Estimated Cost/Hour |
|---------|--------------|---------------------|
| **MSK Serverless** | ~1 MB/s throughput | $2.00 - $3.00 |
| **EMR Serverless** | 2 executors, 4 vCPU each | $1.00 - $2.00 |
| **Lambda** | 4 functions, 512MB-1GB | $0.30 - $0.50 |
| **DynamoDB** | On-demand, light usage | $0.05 - $0.10 |
| **S3** | <1 GB storage, logs | $0.05 - $0.10 |
| **Data Transfer** | Within region | $0.20 - $0.50 |
| **CloudWatch** | Logs and metrics | $0.10 - $0.20 |
| **API Gateway** | <1000 requests | $0.01 - $0.05 |
| **VPC** | Endpoints (no NAT) | $0.10 - $0.20 |
| **TOTAL** | | **$4.00 - $6.00** |

### Cost Drivers

**Highest cost items**:
1. **MSK Serverless**: Charged per GB of data ingested/egressed and per partition-hour
2. **EMR Serverless**: Charged per vCPU-hour and GB-hour
3. **Lambda**: Charged per invocation and GB-second

**Cost scales with**:
- Order generation rate (more orders = more MSK throughput)
- Spark job runtime (longer = more EMR costs)
- Lambda execution time (longer processing = more GB-seconds)
- Data retention (longer = more S3 storage)

## Cost Optimization Strategies

### 1. Use Low-Cost Mode

In `terraform/envs/dev/variables.tf`:
```hcl
variable "low_cost_mode" {
  default = true
}
```

**What it does**:
- Single AZ deployment (no cross-AZ data transfer)
- No NAT gateway (uses VPC endpoints)
- Minimal EMR capacity
- Shorter log retention

**Savings**: ~30-40% reduction

**Trade-offs**:
- Lower availability (single AZ)
- Slower Spark job startup
- Less resilient to failures

### 2. Limit Demo Duration

```bash
# Generate orders for only 5 minutes
aws lambda invoke --function-name streaming-risk-dev-order-generator \
  --payload '{"mode": "normal", "duration_seconds": 300}' \
  response.json
```

**Savings**: Linear with time

### 3. Use Local Docker Compose

For development and testing:
```bash
cd local
docker-compose up
```

**Savings**: $0 AWS costs

**Use for**:
- Code development
- Testing changes
- Learning Kafka/Spark locally

### 4. Stop Spark Job When Not Needed

```bash
# Stop Spark job
aws emr-serverless stop-application --application-id $EMR_APP_ID

# Start when needed
aws emr-serverless start-application --application-id $EMR_APP_ID
```

**Savings**: ~$1-2/hour when stopped

### 5. Reduce Order Generation Rate

```bash
# Lower rate = less MSK throughput
aws lambda invoke --function-name streaming-risk-dev-order-generator \
  --payload '{"mode": "normal", "rate_per_second": 1}' \
  response.json
```

**Savings**: Proportional to rate reduction

### 6. Shorter Log Retention

In Terraform:
```hcl
resource "aws_cloudwatch_log_group" "example" {
  retention_in_days = 1  # Instead of 7
}
```

**Savings**: Minimal, but reduces clutter

### 7. Use Spot Instances (Advanced)

For EMR Serverless, you can't use Spot directly, but you can:
- Reduce executor count
- Use smaller instance sizes
- Stop application between demos

## Cost Monitoring

### Set Up Billing Alerts

```bash
# Create budget alert
aws budgets create-budget \
  --account-id YOUR_ACCOUNT_ID \
  --budget file://budget.json
```

**budget.json**:
```json
{
  "BudgetName": "streaming-risk-controls-demo",
  "BudgetLimit": {
    "Amount": "10",
    "Unit": "USD"
  },
  "TimeUnit": "MONTHLY",
  "BudgetType": "COST"
}
```

### Track Costs by Tag

All resources are tagged with:
```hcl
tags = {
  Project     = "streaming-risk-controls"
  Environment = "dev"
  ManagedBy   = "terraform"
}
```

**View costs**:
```bash
aws ce get-cost-and-usage \
  --time-period Start=2024-03-01,End=2024-03-31 \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=TAG,Key=Project
```

### CloudWatch Cost Dashboard

Create custom dashboard:
1. Go to CloudWatch Console
2. Create dashboard
3. Add Cost Explorer widget
4. Filter by Project tag

## Cleanup Procedures

### Quick Cleanup (Terraform Destroy)

```bash
cd terraform/envs/dev
terraform destroy
```

**What it destroys**:
- All Lambda functions
- MSK cluster
- EMR application
- DynamoDB tables
- S3 bucket (if empty)
- VPC and networking
- IAM roles
- CloudWatch logs and dashboard

**Time**: 5-10 minutes

### Verify Cleanup

```bash
# Check for remaining resources
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Project,Values=streaming-risk-controls

# Should return empty list
```

### Manual Cleanup (If Terraform Fails)

If `terraform destroy` fails, manually delete:

1. **S3 Bucket** (must be empty first):
```bash
aws s3 rm s3://$S3_BUCKET --recursive
aws s3 rb s3://$S3_BUCKET
```

2. **MSK Cluster**:
```bash
aws kafka delete-cluster --cluster-arn $MSK_CLUSTER_ARN
```

3. **EMR Application**:
```bash
aws emr-serverless delete-application --application-id $EMR_APP_ID
```

4. **Lambda Functions**:
```bash
aws lambda delete-function --function-name streaming-risk-dev-order-generator
# Repeat for other functions
```

5. **DynamoDB Tables**:
```bash
aws dynamodb delete-table --table-name streaming-risk-dev-audit-index
aws dynamodb delete-table --table-name streaming-risk-dev-state-cache
```

6. **VPC** (delete in order):
```bash
# Delete NAT gateway (if exists)
# Delete subnets
# Delete route tables
# Delete internet gateway
# Delete VPC
```

### Orphaned Resources to Check

Common resources that may not be cleaned up:

1. **Elastic Network Interfaces (ENIs)**
   - Created by Lambda in VPC
   - Usually auto-deleted, but check

2. **CloudWatch Log Groups**
   - May persist after Lambda deletion
   - Delete manually if needed

3. **S3 Bucket Versions**
   - If versioning enabled
   - Empty all versions before deleting bucket

4. **IAM Roles**
   - Should be deleted by Terraform
   - Check for orphaned roles

**Check command**:
```bash
# List all resources in region
aws resourcegroupstaggingapi get-resources \
  --region us-east-1 \
  --resource-type-filters \
    lambda:function \
    kafka:cluster \
    dynamodb:table \
    s3:bucket
```

## Cost Estimation for Different Scenarios

### Scenario 1: 1-Hour Classroom Demo
- **Setup**: 20 minutes
- **Demo**: 10 minutes
- **Exercises**: 30 minutes
- **Cleanup**: 10 minutes
- **Total AWS runtime**: ~1 hour
- **Estimated cost**: $4-6

### Scenario 2: Full-Day Workshop
- **Setup**: 30 minutes
- **Demos**: 2 hours
- **Student exercises**: 4 hours
- **Cleanup**: 30 minutes
- **Total AWS runtime**: ~7 hours
- **Estimated cost**: $30-45

### Scenario 3: Week-Long Course
- **Daily usage**: 2 hours/day
- **5 days**: 10 hours total
- **Estimated cost**: $40-60

**Optimization**: Use local Docker Compose for 80% of work, AWS for final demos only.

### Scenario 4: Production-Like Load Testing
- **High order rate**: 1000 orders/sec
- **24-hour run**: Full day
- **Multiple accounts**: 100 accounts
- **Estimated cost**: $200-300

**Not recommended for educational demos**

## Free Tier Considerations

### Services with Free Tier

1. **Lambda**
   - 1M requests/month free
   - 400K GB-seconds/month free
   - Demo uses ~10K requests = well within free tier

2. **DynamoDB**
   - 25 GB storage free
   - 25 WCU, 25 RCU free
   - Demo uses <1 GB = within free tier

3. **S3**
   - 5 GB storage free
   - 20K GET, 2K PUT requests free
   - Demo uses <1 GB = within free tier

4. **CloudWatch**
   - 10 custom metrics free
   - 5 GB logs free
   - Demo uses ~1 GB logs = within free tier

### Services WITHOUT Free Tier

1. **MSK Serverless** - No free tier
2. **EMR Serverless** - No free tier
3. **VPC Endpoints** - No free tier (but cheap)
4. **API Gateway** - 1M requests free (first 12 months only)

**Bottom line**: Lambda, DynamoDB, S3, CloudWatch are essentially free for this demo. MSK and EMR are the main costs.

## Cost Comparison: AWS vs Local

| Aspect | AWS | Local Docker |
|--------|-----|--------------|
| **Cost** | $4-6/hour | $0 |
| **Setup Time** | 20-30 min | 5 min |
| **Realism** | Production-like | Simplified |
| **Scalability** | High | Limited |
| **Persistence** | Yes | No (ephemeral) |
| **Best For** | Final demos, testing | Development, learning |

**Recommendation**: Use local for 80% of work, AWS for final validation and demos.

## Emergency Cost Controls

### If Costs Are Unexpectedly High

1. **Immediate**: Stop order generator
```bash
# No way to stop Lambda mid-execution, but don't invoke again
```

2. **Stop Spark job**:
```bash
aws emr-serverless stop-application --application-id $EMR_APP_ID
```

3. **Delete MSK cluster** (biggest cost):
```bash
aws kafka delete-cluster --cluster-arn $MSK_CLUSTER_ARN
```

4. **Full destroy**:
```bash
terraform destroy -auto-approve
```

### Prevent Runaway Costs

1. **Set billing alerts** (see above)
2. **Use low_cost_mode = true**
3. **Limit demo duration**
4. **Destroy immediately after use**
5. **Never leave running overnight**

## Summary

**Key points**:
- Demo costs $4-6 per hour with low_cost_mode
- MSK and EMR are the main cost drivers
- Use local Docker Compose for development
- Always run `terraform destroy` after demo
- Set up billing alerts to avoid surprises
- Check for orphaned resources after cleanup

**Golden rule**: Treat AWS resources like a taxi meter - it's running whenever deployed!
