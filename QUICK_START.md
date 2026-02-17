# Quick Start Guide

Get the SEC Rule 15c3-5 market access controls demo running in 5 minutes (local) or 30 minutes (AWS).

## Local (5 Minutes)

Perfect for learning and development.

```bash
# 1. Start local environment
cd local
docker-compose up -d

# 2. Wait for Kafka to be ready (30 seconds)
docker-compose logs -f kafka

# 3. Access AKHQ UI
open http://localhost:8080

# 4. Watch topics
docker-compose exec kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic orders.v1 \
  --from-beginning
```

**What you get**:
- Kafka running locally
- All topics created
- AKHQ UI for visualization
- Services ready to run

**Limitations**:
- No Spark (simplified Python streaming)
- No AWS services
- Single-node Kafka

## AWS (30 Minutes)

Full production-like deployment.

```bash
# 1. Build Lambda packages
make build-lambdas

# 2. Deploy infrastructure
cd terraform/envs/dev
terraform init
terraform apply  # Type 'yes'

# 3. Create Kafka topics
cd ../../..
export MSK_BOOTSTRAP=$(cd terraform/envs/dev && terraform output -raw msk_bootstrap_brokers)
./tools/create-topics.sh

# 4. Start Spark job
./tools/run-spark-job.sh

# 5. Generate orders
aws lambda invoke \
  --function-name streaming-risk-dev-order-generator \
  --payload '{"mode": "normal", "duration_seconds": 300}' \
  response.json

# 6. Watch orders
./tools/tail-topic.sh orders.v1
```

**What you get**:
- Full serverless stack on AWS
- MSK Serverless (Kafka)
- EMR Serverless (Spark)
- Lambda functions
- API Gateway
- CloudWatch monitoring

**Cost**: ~$4-6 per hour

## Demo Flow (10 Minutes)

Once deployed, run the demo:

```bash
# 1. Normal operation (2 min)
aws lambda invoke --function-name streaming-risk-dev-order-generator \
  --payload '{"mode": "normal", "duration_seconds": 120}' response.json

# Watch: ./tools/tail-topic.sh orders.v1

# 2. Trigger panic mode (3 min)
aws lambda invoke --function-name streaming-risk-dev-order-generator \
  --payload '{"mode": "panic", "account_id": "12345", "duration_seconds": 60}' response.json

# Watch: ./tools/tail-topic.sh risk_signals.v1
# Watch: ./tools/tail-topic.sh killswitch.commands.v1

# 3. Observe enforcement (2 min)
# Watch: ./tools/tail-topic.sh audit.v1
# Look for: "decision": "DROP"

# 4. Manual unkill (2 min)
export API_URL=$(cd terraform/envs/dev && terraform output -raw operator_console_url)
curl -X POST $API_URL/unkill \
  -H "Content-Type: application/json" \
  -d '{"scope": "ACCOUNT:12345", "reason": "Manual override"}'

# Watch: ./tools/tail-topic.sh killswitch.state.v1
# Watch: ./tools/tail-topic.sh audit.v1

# 5. Verify recovery (1 min)
# Orders from account 12345 should now be allowed
```

## Key Commands

### Terraform
```bash
terraform init          # Initialize
terraform plan          # Preview changes
terraform apply         # Deploy
terraform destroy       # Clean up
terraform output        # Show outputs
```

### Kafka Topics
```bash
./tools/create-topics.sh              # Create all topics
./tools/tail-topic.sh <topic-name>    # Watch topic
kafka-topics --list                   # List topics
```

### Lambda
```bash
aws lambda invoke --function-name <name> \
  --payload '{}' response.json

aws logs tail /aws/lambda/<name> --follow
```

### Spark
```bash
./tools/run-spark-job.sh              # Start job
aws emr-serverless list-job-runs \
  --application-id $EMR_APP_ID        # List runs
```

## Troubleshooting

### Kafka not ready
```bash
# Check MSK cluster status
aws kafka describe-cluster --cluster-arn $MSK_CLUSTER_ARN

# Wait for ACTIVE state
```

### Lambda can't connect to MSK
```bash
# Check security groups
aws ec2 describe-security-groups --group-ids <sg-id>

# Check VPC configuration
aws lambda get-function-configuration --function-name <name>
```

### Spark job fails
```bash
# Check job status
aws emr-serverless get-job-run \
  --application-id $EMR_APP_ID \
  --job-run-id <job-run-id>

# Check logs in S3
aws s3 ls s3://$S3_BUCKET/spark-logs/
```

### High costs
```bash
# Destroy immediately
cd terraform/envs/dev
terraform destroy

# Check for orphaned resources
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Project,Values=streaming-risk-controls
```

## Next Steps

- **Learn**: Read [docs/00-overview.md](docs/00-overview.md)
- **Deploy**: Follow [docs/02-deploy-aws.md](docs/02-deploy-aws.md)
- **Demo**: Run [docs/03-run-demo.md](docs/03-run-demo.md)
- **Exercises**: Try [docs/05-exercises.md](docs/05-exercises.md)
- **Blog**: Read [blog/posts/sec-15c3-5-market-access-controls.md](blog/posts/sec-15c3-5-market-access-controls.md)

## Getting Help

- Check [docs/06-troubleshooting.md](docs/06-troubleshooting.md)
- Review CloudWatch Logs
- Use `./tools/tail-topic.sh` to debug
- Open an issue on GitHub

## Cleanup

**Always clean up after demo to avoid charges!**

```bash
cd terraform/envs/dev
terraform destroy
```

Verify:
```bash
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Project,Values=streaming-risk-controls
```

Should return empty list.
