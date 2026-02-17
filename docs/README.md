# Workshop Documentation

Complete guide to deploying, running, and learning from the streaming risk controls demo.

## Quick Navigation

### Getting Started
1. [00-overview.md](00-overview.md) - **Start here**: Architecture and concepts
2. [01-prereqs.md](01-prereqs.md) - Prerequisites and setup
3. [QUICK_START.md](../QUICK_START.md) - 5-minute local or 30-minute AWS setup

### Deployment
4. [02-deploy-aws.md](02-deploy-aws.md) - Complete AWS deployment guide
5. [02-deploy-local.md](02-deploy-local.md) - Local Docker Compose setup (coming soon)

### Running the Demo
6. [03-run-demo.md](03-run-demo.md) - 10-12 minute demo script for classroom

### Operations
7. [04-observe.md](04-observe.md) - Observability, monitoring, and debugging
8. [06-troubleshooting.md](06-troubleshooting.md) - Common issues and solutions
9. [07-cost-and-cleanup.md](07-cost-and-cleanup.md) - Cost management and cleanup

### Learning
10. [05-exercises.md](05-exercises.md) - 10 student exercises
11. [08-security-notes.md](08-security-notes.md) - Security considerations
12. [../blog/posts/sec-15c3-5-market-access-controls.md](../blog/posts/sec-15c3-5-market-access-controls.md) - Blog post with regulatory context

## Documentation Structure

### Architecture Documentation
- **00-overview.md**: Deep dive into system architecture
  - Control plane vs data plane
  - Kafka topics and schemas
  - Kill switch scopes
  - Compaction explained
  - Spark streaming job
  - DynamoDB tables
  - Security model

### Setup Documentation
- **01-prereqs.md**: What you need before starting
  - Required tools (AWS CLI, Terraform, Docker, Python)
  - AWS permissions
  - Cost estimates
  - Knowledge prerequisites

### Deployment Documentation
- **02-deploy-aws.md**: Step-by-step AWS deployment
  - Build Lambda packages
  - Initialize Terraform
  - Deploy infrastructure
  - Create Kafka topics
  - Start Spark job
  - Verify system

### Demo Documentation
- **03-run-demo.md**: Live classroom demo script
  - Setup (before class)
  - Part 1: Architecture overview (2 min)
  - Part 2: Normal operation (2 min)
  - Part 3: Trigger panic mode (3 min)
  - Part 4: Enforcement (2 min)
  - Part 5: Manual recovery (2 min)
  - Part 6: Kafka compaction (1 min)
  - Key takeaways
  - Q&A topics

### Operations Documentation
- **04-observe.md**: Monitoring and observability
  - Kafka topic consumption
  - CloudWatch Logs queries
  - CloudWatch Metrics
  - DynamoDB queries
  - Spark job monitoring
  - Correlation ID tracing
  - Performance monitoring
  - Alerting setup

- **06-troubleshooting.md**: Problem solving
  - Deployment issues
  - Kafka issues
  - Lambda issues
  - Spark issues
  - Networking issues
  - Cost issues
  - Common error messages

- **07-cost-and-cleanup.md**: Cost management
  - Cost breakdown
  - Cost optimization strategies
  - Cost monitoring
  - Cleanup procedures
  - Orphaned resources
  - Cost estimates for different scenarios

### Learning Documentation
- **05-exercises.md**: Hands-on exercises
  - Exercise 1: Symbol-level kill switch (Beginner)
  - Exercise 2: Throttling (Intermediate)
  - Exercise 3: Deduplication (Intermediate)
  - Exercise 4: Multi-window detection (Advanced)
  - Exercise 5: Auto-unkill with cooldown (Advanced)
  - Exercise 6: Real-time dashboard (Advanced)
  - Exercise 7: Strategy-level controls (Intermediate)
  - Exercise 8: Latency optimization (Advanced)
  - Exercise 9: Chaos engineering (Advanced)
  - Exercise 10: Regulatory reporting (Intermediate)

- **08-security-notes.md**: Security considerations
  - Educational demo vs production
  - Threat model
  - IAM security
  - Network security
  - Data security
  - API security
  - Audit and compliance
  - Secrets management
  - Incident response
  - Recommendations for production

## Reading Paths

### For Instructors

**Preparation** (1 hour):
1. Read 00-overview.md (architecture)
2. Read 03-run-demo.md (demo script)
3. Review blog post (regulatory context)
4. Practice demo locally

**Deployment** (30 minutes):
1. Follow 01-prereqs.md (setup)
2. Follow 02-deploy-aws.md (deploy)
3. Test demo flow

**Teaching** (10-12 minutes):
1. Use 03-run-demo.md as script
2. Show architecture diagram
3. Demonstrate panic mode trigger
4. Show enforcement and recovery

### For Students

**Week 1 - Understanding** (2-3 hours):
1. Read 00-overview.md (architecture)
2. Read blog post (context)
3. Watch demo (in class)
4. Deploy locally (Docker Compose)

**Week 2 - Deployment** (2-3 hours):
1. Review 01-prereqs.md (setup)
2. Follow 02-deploy-aws.md (deploy)
3. Run demo yourself
4. Explore with 04-observe.md

**Week 3 - Exercises** (4-6 hours):
1. Choose 2-3 exercises from 05-exercises.md
2. Implement and test
3. Document your work
4. Submit for review

**Week 4 - Advanced** (4-6 hours):
1. Complete advanced exercises
2. Read 08-security-notes.md
3. Propose improvements
4. Present findings

### For Self-Learners

**Day 1 - Quick Start** (1 hour):
1. Read QUICK_START.md
2. Deploy locally
3. Explore Kafka topics

**Day 2 - Deep Dive** (2-3 hours):
1. Read 00-overview.md
2. Read blog post
3. Understand regulatory context

**Day 3 - AWS Deployment** (2-3 hours):
1. Follow 02-deploy-aws.md
2. Run demo
3. Observe with 04-observe.md

**Day 4-7 - Exercises** (8-12 hours):
1. Complete beginner exercises
2. Try intermediate exercises
3. Challenge yourself with advanced

## Key Concepts by Document

### Architecture Concepts
- **00-overview.md**: Control plane, data plane, compaction, scopes
- **Blog post**: Regulatory requirements, Knight Capital, SEC Rule 15c3-5

### Operational Concepts
- **04-observe.md**: Correlation IDs, metrics, logs, tracing
- **06-troubleshooting.md**: Debugging workflows, common issues
- **07-cost-and-cleanup.md**: Cost optimization, resource management

### Security Concepts
- **08-security-notes.md**: Threat modeling, IAM, encryption, compliance

### Implementation Concepts
- **02-deploy-aws.md**: Terraform, Lambda packaging, Kafka topics
- **05-exercises.md**: Throttling, deduplication, multi-window detection

## Diagrams

### Architecture Diagram
See 00-overview.md for:
- High-level system architecture
- Topic flow diagram
- Compaction visualization

### Sequence Diagrams
See 03-run-demo.md for:
- Normal operation flow
- Panic mode trigger flow
- Kill switch enforcement flow

### Mermaid Diagrams
All diagrams use Mermaid syntax and can be:
- Viewed in GitHub
- Rendered in VS Code (with Mermaid extension)
- Exported to PNG/SVG

## Code Examples

### Kafka Consumption
See 04-observe.md for:
- kcat examples
- kafka-console-consumer examples
- Topic monitoring commands

### CloudWatch Queries
See 04-observe.md for:
- CloudWatch Insights queries
- Metric queries
- Log filtering

### DynamoDB Queries
See 04-observe.md for:
- Query by order ID
- Query by account
- Scan for dropped orders

### Terraform Examples
See 02-deploy-aws.md for:
- Module usage
- Variable configuration
- Output queries

## Troubleshooting Index

Quick links to common issues:

- **Deployment fails**: [06-troubleshooting.md#deployment-issues](06-troubleshooting.md#deployment-issues)
- **Kafka connection**: [06-troubleshooting.md#kafka-issues](06-troubleshooting.md#kafka-issues)
- **Lambda timeout**: [06-troubleshooting.md#lambda-issues](06-troubleshooting.md#lambda-issues)
- **Spark job fails**: [06-troubleshooting.md#spark-issues](06-troubleshooting.md#spark-issues)
- **High costs**: [07-cost-and-cleanup.md#unexpected-high-costs](07-cost-and-cleanup.md#unexpected-high-costs)
- **Security groups**: [06-troubleshooting.md#networking-issues](06-troubleshooting.md#networking-issues)

## Additional Resources

### External Documentation
- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [Apache Spark Structured Streaming](https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html)
- [AWS Lambda Developer Guide](https://docs.aws.amazon.com/lambda/latest/dg/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)

### Regulatory Resources
- [SEC Rule 15c3-5](https://www.sec.gov/files/rules/final/2010/34-63241.pdf)
- [SEC Compliance Guide](https://www.sec.gov/files/rules/final/2010/34-63241-secg.htm)

### Related Topics
- Event-driven architecture
- Stream processing patterns
- Kafka compaction
- Serverless architectures
- Financial market infrastructure

## Contributing to Documentation

See [CONTRIBUTING.md](../CONTRIBUTING.md) for:
- Documentation style guide
- How to add new docs
- How to improve existing docs
- Markdown formatting guidelines

## Feedback

Documentation feedback is welcome:
- Open a GitHub Issue for errors or unclear sections
- Submit a Pull Request for improvements
- Suggest new topics or exercises

## Version History

- **v1.0** (2024-03): Initial release
  - Complete architecture documentation
  - AWS deployment guide
  - 10 student exercises
  - Blog post with regulatory context

---

**Next Steps**:
- New to the project? Start with [00-overview.md](00-overview.md)
- Ready to deploy? Go to [02-deploy-aws.md](02-deploy-aws.md)
- Want to run the demo? See [03-run-demo.md](03-run-demo.md)
- Need help? Check [06-troubleshooting.md](06-troubleshooting.md)
