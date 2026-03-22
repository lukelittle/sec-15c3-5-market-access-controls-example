# SEC Rule 15c3-5: Market Access Controls

On August 1, 2012, Knight Capital deployed untested trading software to production. Within 45 minutes, a runaway algorithm executed millions of erroneous trades. There was no centralized kill switch. No way to stop all servers at once. By the time they pulled the plug, Knight had lost $440 million — more than the company's entire market cap. They were acquired at a fire-sale price six months later.

This project builds the system that could have prevented that outcome.

## What This Is

A complete, working implementation of real-time market access controls as required by SEC Rule 15c3-5. Orders flow through the system. A Spark Structured Streaming job watches for anomalies in 60-second windows. When thresholds are breached, a kill switch automatically blocks the offending account. A human operator must explicitly review and restore access. Every decision is audited.

The same architectural patterns shown here — streaming analytics, event-driven microservices, kill switches, audit trails — are used across industries wherever systems need to detect anomalies and act on them in real time: fraud detection, infrastructure monitoring, IoT alerting, content moderation, and more.

## Why This Matters for Your Career

The technologies in this project are not academic exercises. They are the tools companies are hiring for right now:

- **Kafka** is the backbone of real-time data at LinkedIn, Netflix, Uber, and most major banks
- **Spark Streaming** powers fraud detection at Capital One, risk analytics at Goldman Sachs, and recommendation engines at Pinterest
- **AWS managed services** (MSK, EMR, Lambda) are how teams ship these systems without managing infrastructure
- **Infrastructure as Code** (Terraform) is a baseline expectation for cloud engineering roles
- **Event-driven architecture** is the dominant pattern for building systems that scale

If you can build, deploy, and reason about a system like this one, you can walk into an interview for a data engineer, platform engineer, or cloud architect role and speak from experience.

## Architecture

```
                    ┌─────────────────┐
                    │ Order Generator  │
                    │   (Lambda/Local) │
                    └────────┬────────┘
                             │
                             ▼
                      ┌─────────────┐
                      │  orders.v1  │ ◄── Kafka Topic
                      └──────┬──────┘
                             │
                ┌────────────┼────────────┐
                │                         │
                ▼                         ▼
    ┌───────────────────┐     ┌───────────────────┐
    │   Spark Streaming │     │   Order Router     │
    │   Risk Detector   │     │   (Lambda/Local)   │
    └────────┬──────────┘     └──┬──────────┬──────┘
             │                   │          │
             ▼                   ▼          ▼
  ┌──────────────────────┐  ┌────────┐  ┌─────────┐
  │killswitch.commands.v1│  │gated.v1│  │audit.v1 │
  └──────────┬───────────┘  └────────┘  └─────────┘
             │
             ▼
  ┌───────────────────────┐
  │ Kill Switch Aggregator│
  │   (Lambda/Local)      │
  └──────────┬────────────┘
             │
             ▼
  ┌──────────────────────┐     ┌───────────────────┐
  │killswitch.state.v1   │◄────│ Operator Console  │
  │   (compacted)        │     │ POST /kill /unkill │
  └──────────────────────┘     └───────────────────┘
```

**Detection** (Spark) is separate from **Enforcement** (Order Router) is separate from **Control** (Operator Console). Kafka is the backbone connecting all three.

## Quick Start

### Local Development (Free, 2 minutes)

```bash
cd local
docker compose up --build -d
```

This starts Kafka, all four services, the Spark risk detector, and a Kafka UI. No AWS account needed.

- **AKHQ** (Kafka UI): http://localhost:8080
- **Operator Console**: http://localhost:8000

Test it:

```bash
# Check the system is running
curl http://localhost:8000/health

# Manually kill an account
curl -X POST http://localhost:8000/kill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"ACCOUNT:12345","reason":"suspicious activity"}'

# Watch orders get dropped
docker compose logs order-router --tail 20

# Unkill the account
curl -X POST http://localhost:8000/unkill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"ACCOUNT:12345","reason":"cleared after review"}'
```

### AWS Deployment ($4-6/hour)

See [AWS Deployment Guide](docs/03-deploy-aws.md) for full instructions.

```bash
make build
cd terraform/envs/dev
terraform init && terraform apply
```

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture Overview](docs/00-overview.md) | System design, data flow, Kafka topics, kill switch mechanics |
| [Prerequisites](docs/01-prereqs.md) | What you need installed for local and AWS |
| [Local Development](docs/02-local-development.md) | Docker Compose setup, testing, troubleshooting |
| [AWS Deployment](docs/03-deploy-aws.md) | Terraform deployment, MSK, EMR, Lambda setup |
| [Presentation Guide](docs/04-presentation-guide.md) | 30-45 minute talk outline with speaker notes |
| [Demo Script](docs/05-run-demo.md) | Step-by-step demo for live presentation |
| [Observability](docs/06-observe.md) | Monitoring, log queries, tracing |
| [Exercises](docs/07-exercises.md) | 10 student exercises from beginner to advanced |
| [Cost and Cleanup](docs/08-cost-and-cleanup.md) | AWS cost breakdown and cleanup procedures |
| [Troubleshooting](docs/09-troubleshooting.md) | Common issues and solutions |
| [Security Notes](docs/10-security-notes.md) | What's production-ready and what's not |

## Cost

| Environment | Cost | Best For |
|-------------|------|----------|
| **Local** (Docker Compose) | **$0** | Development, testing, classroom demos |
| **AWS** (1-hour demo) | ~$5 | Showing real cloud services |
| **AWS** (full-day workshop) | ~$35 | Extended hands-on sessions |

Deploy right before you need it, `terraform destroy` right after. See [Cost and Cleanup](docs/08-cost-and-cleanup.md) for a detailed per-service breakdown.

## Repository Structure

```
.
├── services/                  # Python services (Lambda handlers + local versions)
│   ├── order_generator/       # Produces synthetic orders
│   ├── killswitch_aggregator/ # Maintains kill switch state
│   ├── order_router/          # Enforces kill switch on every order
│   └── operator_console/      # REST API for manual control
├── spark/                     # PySpark streaming risk detector
│   └── risk_job/
├── local/                     # Docker Compose for local development
│   └── docker-compose.yml
├── terraform/                 # Infrastructure as Code
│   ├── modules/               # Reusable Terraform modules
│   └── envs/dev/              # Development environment
├── tools/                     # Helper scripts
├── docs/                      # Full documentation
├── tests/                     # Integration tests
└── blog/                      # Blog post content
```

## Blog Post

Read the full context and motivation: [Designing Pre-Trade Risk Controls on AWS (SEC Rule 15c3-5)](https://lukelittle.com/posts/2026/02/designing-pre-trade-risk-controls-on-aws-sec-rule-15c3-5/)

## Educational Context

Built for ITCS 6190/8190 (Cloud Computing for Data Analysis) at UNC Charlotte. The system ties together concepts students encounter throughout the course:

- **Spark Structured Streaming** -- windowed aggregations, watermarks, checkpoints
- **Kafka** -- topics, consumer groups, log compaction, partitioning
- **AWS Managed Services** -- MSK, EMR Serverless, Lambda, DynamoDB, API Gateway
- **Event-Driven Architecture** -- separation of concerns, audit trails, correlation IDs
- **Infrastructure as Code** -- Terraform modules, least-privilege IAM

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

This software is provided for educational purposes only and should not be used in production trading systems without extensive additional development, testing, and regulatory review.
