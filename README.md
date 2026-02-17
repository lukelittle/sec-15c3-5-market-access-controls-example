# SEC Rule 15c3-5 Market Access Controls Example

**A hands-on demonstration of pre-trade risk controls using Apache Kafka and Apache Spark**

## Overview

This project demonstrates how to build a serverless streaming risk control system that meets SEC Rule 15c3-5 requirements for broker-dealer market access. You'll deploy a complete event-driven architecture on AWS that detects risky trading patterns in real-time using Spark SQL, enforces kill switches through Kafka's compacted topics, and maintains a full audit trail.

The demo connects regulatory requirements to concrete architectural patterns, drawing lessons from the Knight Capital incident of 2012 where the lack of centralized control mechanisms led to $440 million in losses in 45 minutes.

## Architecture

![Architecture Diagram](designing-pre-trade-risk-controls-on-aws.png)

The system implements a separation of concerns between detection, control, and enforcement:

- **Detection Layer**: Spark Structured Streaming analyzes order patterns using SQL windows to compute risk signals
- **Control Plane**: Kafka compacted topics maintain authoritative kill switch state with full audit history
- **Enforcement Layer**: Order router validates every order against current kill state before routing
- **Audit Trail**: Immutable Kafka logs and DynamoDB indexes provide complete traceability

## Key Concepts

### Control Plane vs Data Plane

The architecture separates control from data flow:

- **Control Plane**: Operator console and kill switch aggregator manage authoritative kill state
- **Data Plane**: Order router enforces kill state on every order in real-time
- **Detection**: Spark analyzes patterns and suggests actions, but doesn't directly enforce

This separation ensures consistent enforcement even if detection systems fail or are delayed.

### Kafka Compaction for Kill State

The `killswitch.state.v1` topic uses Kafka's log compaction to maintain the latest kill status per scope (GLOBAL, ACCOUNT:xxx, SYMBOL:xxx):

- **Single source of truth**: Latest state is always available to all consumers
- **Replayability**: New services can bootstrap current state by reading the entire topic
- **Auditability**: Commands topic retains full history of all state changes

### Regulatory Context

Real broker-dealers must comply with SEC Rule 15c3-5 (Market Access Rule), which requires:

- Pre-trade risk controls to prevent erroneous orders
- "Direct and exclusive control" over market access
- Supervisory procedures and audit trails

This demo implements these patterns using modern streaming architecture:

- **Direct control**: Centralized kill switch with authoritative state
- **Real-time enforcement**: Every order checked before routing
- **Audit trail**: Immutable log of all decisions with correlation IDs

## Quick Start

### AWS Deployment (30 minutes)

**Prerequisites:**
- AWS account with appropriate permissions
- AWS CLI configured
- Terraform 1.6 or later
- Python 3.11 or later
- Docker

**Deploy:**

```bash
# Build Lambda packages
make build

# Deploy infrastructure
cd terraform/envs/dev
terraform init
terraform apply

# Create Kafka topics
export MSK_BOOTSTRAP=$(terraform output -raw msk_bootstrap_brokers)
cd ../../..
./tools/create-topics.sh

# Deploy Spark job
./tools/deploy-spark-job.sh
```

### Local Development (5 minutes)

For quick iteration without AWS costs:

```bash
cd local
docker-compose up -d

# Access AKHQ UI at http://localhost:8080
```

## Running the Demo

### Normal Operation

```bash
# Start order generator (normal mode)
aws lambda invoke --function-name sec-15c3-5-dev-order-generator \
  --payload '{"mode": "normal", "duration_seconds": 300}' \
  response.json

# Watch orders flowing
./tools/tail-topic.sh orders.v1
```

### Trigger Kill Switch

```bash
# Trigger panic mode (high order rate)
aws lambda invoke --function-name sec-15c3-5-dev-order-generator \
  --payload '{"mode": "panic", "account_id": "12345", "duration_seconds": 60}' \
  response.json

# Watch Spark detect breach and emit kill command
./tools/tail-topic.sh killswitch.commands.v1

# Verify orders are dropped
./tools/tail-topic.sh audit.v1
```

### Manual Recovery

```bash
# Operator unkills via console
export API_URL=$(cd terraform/envs/dev && terraform output -raw operator_console_url)
curl -X POST $API_URL/unkill \
  -H "Content-Type: application/json" \
  -d '{"scope": "ACCOUNT:12345", "reason": "Manual override after review"}'
```

## Testing

Run integration tests to verify the system works:

```bash
# Test AWS deployment
./tests/integration/test_demo_flow.sh

# Test local Docker setup
./tests/integration/test_local_stack.sh
```

## Documentation

Comprehensive guides are available in the `docs/` directory:

- [Architecture Overview](docs/00-overview.md) - Deep dive into system design
- [Prerequisites](docs/01-prereqs.md) - Setup requirements
- [AWS Deployment](docs/02-deploy-aws.md) - Step-by-step deployment guide
- [Demo Script](docs/03-run-demo.md) - 10-12 minute classroom demo
- [Observability](docs/04-observe.md) - Monitoring and debugging
- [Exercises](docs/05-exercises.md) - Hands-on learning exercises
- [Troubleshooting](docs/06-troubleshooting.md) - Common issues and solutions
- [Cost Management](docs/07-cost-and-cleanup.md) - Cost optimization and cleanup
- [Security Notes](docs/08-security-notes.md) - Security considerations

## Blog Post

Read the full context and motivation: [Designing Pre-Trade Risk Controls on AWS (SEC Rule 15c3-5)](blog/posts/sec-15c3-5-market-access-controls.md)

## Repository Structure

```
.
├── terraform/              # Infrastructure as Code
│   ├── modules/           # Reusable Terraform modules
│   └── envs/dev/          # Development environment
├── services/              # Lambda functions
│   ├── order_generator/
│   ├── killswitch_aggregator/
│   ├── order_router/
│   └── operator_console/
├── spark/                 # PySpark streaming job
│   └── risk_job/
├── local/                 # Docker Compose for local dev
├── tools/                 # Helper scripts
├── docs/                  # Workshop documentation
├── tests/                 # Integration tests
└── blog/                  # Blog post content
```

## Cost Estimates

Typical costs for running the demo:

- **1-hour demo**: $4-6
- **Full-day workshop**: $30-45
- **Local development**: $0

Cost breakdown:
- MSK Serverless: $2-3/hour
- EMR Serverless: $1-2/hour
- Lambda: $0.50/hour (mostly free tier)
- Other services: $0.50/hour

See [Cost Management](docs/07-cost-and-cleanup.md) for optimization strategies.

## Cleanup

Always destroy infrastructure after use to avoid charges:

```bash
cd terraform/envs/dev
terraform destroy

# Verify no resources remain
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Project,Values=sec-15c3-5-market-access-controls
```

## Security Disclaimer

This is an educational demonstration, not production trading software:

- Uses synthetic data only
- No real brokerage connectivity
- Simplified security model for learning
- Not intended for actual trading decisions

For production use, additional controls are required:
- Encryption at rest and in transit
- Comprehensive authentication and authorization
- Rate limiting and DDoS protection
- Security scanning and penetration testing
- Disaster recovery procedures
- Compliance certifications

See [Security Notes](docs/08-security-notes.md) for detailed discussion.

## Learning Objectives

This project teaches:

- Event-driven architecture with Kafka
- Stream processing with Spark SQL
- Serverless deployment with Terraform
- Regulatory compliance patterns
- Operational patterns (audit trails, correlation IDs, idempotency)
- Real-world incident analysis

## Acknowledgments

Built for data and cloud computing education at UNC Charlotte. Inspired by SEC Rule 15c3-5 market access requirements and lessons learned from the Knight Capital incident (2012).

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) file for details.

Educational use disclaimer: This software is provided for educational purposes only and should not be used in production trading systems without extensive additional development, testing, and regulatory review.
