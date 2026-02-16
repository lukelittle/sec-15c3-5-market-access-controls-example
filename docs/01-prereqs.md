# Prerequisites

## Required Tools

### AWS Deployment

1. **AWS Account**
   - Active AWS account with appropriate permissions
   - Ability to create: VPC, MSK, Lambda, EMR, DynamoDB, S3, IAM roles
   - Estimated cost: $4-6 per hour of demo runtime

2. **AWS CLI** (>= 2.0)
   ```bash
   # Install
   brew install awscli  # macOS
   # or download from https://aws.amazon.com/cli/
   
   # Configure
   aws configure
   ```

3. **Terraform** (>= 1.6)
   ```bash
   # Install
   brew install terraform  # macOS
   # or download from https://www.terraform.io/downloads
   
   # Verify
   terraform version
   ```

4. **Python** (>= 3.11)
   ```bash
   # Verify
   python3 --version
   
   # Install pip if needed
   python3 -m ensurepip --upgrade
   ```

5. **Docker** (for Lambda packaging)
   ```bash
   # Install Docker Desktop
   # https://www.docker.com/products/docker-desktop
   
   # Verify
   docker --version
   ```

6. **Kafka CLI Tools** (optional but recommended)
   ```bash
   # Install kcat (formerly kafkacat)
   brew install kcat  # macOS
   
   # Or install Kafka binaries
   brew install kafka  # macOS
   ```

### Local Development

1. **Docker Compose**
   - Included with Docker Desktop
   - Verify: `docker-compose --version`

2. **Python 3.11+** with pip

3. **Make** (optional, for convenience)
   - Pre-installed on macOS/Linux
   - Windows: Install via chocolatey or use WSL

## AWS Permissions

Your AWS IAM user/role needs permissions to create:

- **VPC**: Subnets, security groups, route tables, VPC endpoints
- **MSK**: Serverless clusters
- **Lambda**: Functions, layers, event source mappings
- **IAM**: Roles and policies
- **S3**: Buckets and objects
- **DynamoDB**: Tables
- **EMR**: Serverless applications and job runs
- **API Gateway**: HTTP APIs
- **CloudWatch**: Log groups, dashboards

### Recommended IAM Policy

For educational/demo purposes, you can use:
- `PowerUserAccess` (allows most operations except IAM user management)
- Plus `IAMFullAccess` (for creating service roles)

For production, use least-privilege policies.

## Cost Considerations

### Estimated Costs (1-hour demo)

- **MSK Serverless**: ~$2-3 (based on throughput)
- **EMR Serverless**: ~$1-2 (based on vCPU-hours)
- **Lambda**: <$0.50 (mostly within free tier)
- **DynamoDB**: <$0.10 (on-demand pricing)
- **Data Transfer**: <$0.50
- **S3**: <$0.10
- **Total**: ~$4-6 per hour

### Cost Optimization Tips

1. **Use low_cost_mode = true** in Terraform
   - Single AZ deployment
   - Minimal capacity settings
   - No NAT gateway (uses VPC endpoints)

2. **Destroy infrastructure immediately after demo**
   ```bash
   terraform destroy
   ```

3. **Use local Docker Compose for development**
   - No AWS costs
   - Faster iteration

4. **Set billing alerts**
   ```bash
   aws budgets create-budget \
     --account-id YOUR_ACCOUNT_ID \
     --budget file://budget.json
   ```

### Free Tier Considerations

Some services have free tiers:
- **Lambda**: 1M requests/month, 400K GB-seconds
- **DynamoDB**: 25 GB storage, 25 WCU, 25 RCU
- **S3**: 5 GB storage, 20K GET requests, 2K PUT requests
- **CloudWatch**: 10 custom metrics, 5 GB logs

MSK and EMR Serverless do NOT have free tiers.

## Network Requirements

### AWS Deployment
- Outbound internet access for:
  - Terraform provider downloads
  - Python package installation (pip)
  - AWS API calls

### Local Development
- Docker daemon running
- Ports available: 9092 (Kafka), 8080 (AKHQ UI)

## Knowledge Prerequisites

### Required
- Basic understanding of:
  - Event-driven architecture
  - Kafka topics and consumers
  - AWS services (Lambda, VPC basics)
  - Command line usage

### Helpful but Not Required
- Spark Structured Streaming
- Terraform syntax
- Python programming
- Financial markets concepts

## Verification Checklist

Before proceeding, verify:

```bash
# AWS CLI configured
aws sts get-caller-identity

# Terraform installed
terraform version

# Python 3.11+
python3 --version

# Docker running
docker ps

# Make available (optional)
make --version
```

## Next Steps

Once prerequisites are met:
- [02-deploy-aws.md](02-deploy-aws.md): Deploy to AWS
- [02-deploy-local.md](02-deploy-local.md): Run locally with Docker Compose
