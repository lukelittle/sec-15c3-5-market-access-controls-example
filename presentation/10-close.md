# Section 10: Career Relevance, Q&A, and Close

**Duration:** 4 minutes + Q&A
**Goal:** Connect the technical content to their careers, handle questions, end strong.

---

## Career Relevance (2 minutes)

> "Last thing before we open it up for questions. I want to talk about why this matters for your career."

### The Technologies

> "These aren't academic technologies. Kafka is running at LinkedIn, Netflix, Uber, every major bank. Spark Streaming powers fraud detection at Capital One, anomaly detection at Netflix, log processing at Apple. Terraform is on every cloud engineering job listing I've seen in the last three years."

> "If you put 'Spark Structured Streaming,' 'Kafka,' or 'Terraform' on your resume and can talk about them in an interview, you're ahead of 90% of applicants."

### The Patterns

> "But the technologies are less important than the patterns. Technologies change. Kafka might be replaced by Pulsar or Redpanda. Spark might be replaced by Flink. But the patterns we covered today show up everywhere:"

- **Event-driven architecture** — Kafka as a backbone connecting loosely coupled services. This is how Netflix, Uber, and every major fintech company builds their systems.
- **Streaming detection** — Windowed aggregations over real-time data. This is fraud detection at banks, anomaly detection in infrastructure monitoring, content moderation at social media companies.
- **Kill switches** — The ability to immediately halt a subsystem. Every production system at every serious company has circuit breakers, feature flags, or kill switches. If you've used Istio, Envoy, or LaunchDarkly, you've seen this pattern.
- **Audit trails** — Immutable logs of every decision. This is compliance in finance, HIPAA in healthcare, SOC2 in SaaS. Every regulated industry needs this.
- **Separation of detection, control, and enforcement** — This is just good system design. Detection can evolve independently. Enforcement can scale independently. Control is the contract between them.

### The Interview Angle

> "If you're interviewing for a backend, data engineering, or platform engineering role, you will be asked system design questions. 'Design a fraud detection system.' 'Design a rate limiter.' 'Design a feature flag system.' The system we just walked through touches all of those."

> "Being able to say 'I built a real-time risk detection pipeline with Spark Structured Streaming that feeds into a kill switch system backed by Kafka compaction' — that's a complete sentence that covers streaming, event-driven architecture, and distributed state management. That's a strong interview answer."

---

## Call to Action (1 minute)

> "The repo is public. Everything I showed you today is there."

```
git clone https://github.com/lukelittle/sec-15c3-5-market-access-controls-example.git
cd sec-15c3-5-market-access-controls-example/local
docker compose up --build -d
```

> "Three commands. Two minutes. You'll have Kafka, Spark, four microservices, and a web UI running on your laptop."

> "There are 10 exercises in the repo. If you're looking for a course project extension, a portfolio piece, or just want to learn Kafka and Spark with real code instead of word count examples — start there."

> "Questions?"

---

## Q&A Preparation

### Likely Questions and Answers

**"What happens if Kafka goes down?"**
> "In production on AWS, MSK is multi-AZ with replication factor 3 — it's designed not to go down. Locally, if Kafka dies, everything stops. Kafka is the backbone. That's a deliberate architectural choice: one highly-available component rather than point-to-point connections between services. In the chaos testing exercise, you can try restarting Kafka and see what recovers automatically."

**"Why not use a database for kill state?"**
> "You could. DynamoDB, Redis, Postgres — all valid. But Kafka compaction gives you real-time pub/sub AND durable state in one system. The router doesn't need a database connection, doesn't need to handle database failover, doesn't need separate credentials. One protocol, one failure domain. The AWS version of this system actually does use DynamoDB as a cache alongside Kafka, for services that need request-response access to state."

**"How does this scale?"**
> "Kafka scales horizontally — add partitions, add brokers. Spark scales horizontally — add executors. Lambda scales automatically. The architecture doesn't change. The bottleneck in practice is the state lookup in the router, and that's an in-memory dictionary — it scales with memory, which is cheap. The hard part is the architecture design, not the scaling."

**"Is this real production code?"**
> "No. It's educational. Production adds: TLS everywhere, API authentication and authorization, secrets management (no hardcoded passwords), disaster recovery (multi-region), monitoring and alerting (CloudWatch, PagerDuty), rate limiting on the API, input sanitization. The security notes doc in the repo lists everything that's missing. But the patterns — the architecture, the data flows, the separation of concerns — those are real."

**"Could you use Flink instead of Spark?"**
> "Absolutely. Flink is actually better for low-latency streaming — it processes record-by-record rather than in micro-batches like Spark. We used Spark because that's what you've been learning in this course. The architecture doesn't change. Swap Spark for Flink, the same windowed aggregations happen, the same kill commands come out."

**"What about exactly-once semantics?"**
> "Kafka supports exactly-once with idempotent producers and transactional consumers. Spark Structured Streaming has built-in exactly-once guarantees with checkpointing. The router achieves effective exactly-once through deterministic routing: same state + same order = same decision. If a message is replayed, the same ALLOW or DROP decision happens again, and the audit event is a duplicate but harmless."

**"How long did this take to build?"**
> "The services are maybe 2,000 lines of Python. The Terraform is about 2,000 lines of HCL across 8 modules. A few weeks of focused work for the full AWS deployment. The local Docker Compose version is simpler — the compose file is 150 lines, and the local service versions are shorter than the AWS versions because they skip IAM auth and DynamoDB."

### If Nobody Asks Questions

Have 2-3 questions ready to ask THEM:

1. "If you were building this system, what would you add first? A dashboard? Better detection? Multi-region failover?"
2. "Which exercise looks most interesting to you? If you're thinking about course projects, these patterns could extend into something substantial."
3. "Where else could you apply this pattern of streaming detection + kill switch? Think beyond finance — what other domains have the same problem of 'detect anomaly, stop immediately?'" (Answers: infrastructure monitoring, content moderation, IoT fleet management, autonomous vehicles)

---

## Closing Line

End with something that connects back to the opening story:

> "Knight Capital lost $440 million in 45 minutes because they couldn't stop their system. Today, you've seen how to build one that can be stopped in under a second. The code is open source. Go build something with it."

---

## After the Talk

- Leave Docker Compose running if students want to try things during a break
- Share the repo URL in the class chat/Slack/forum
- Offer to answer questions over email or office hours
- If students want to use this for course projects, point them to the exercises and the contributing guide

---

## Complete Timing Summary

| Section | File | Duration | Running Total |
|---------|------|----------|---------------|
| Introduction + Knight Capital | `01-introduction.md` | 7 min | 7 min |
| SEC Rule 15c3-5 | `02-the-rule.md` | 4 min | 11 min |
| System Architecture | `03-architecture.md` | 5 min | 16 min |
| Kafka Deep Dive | `04-kafka-deep-dive.md` | 4 min | 20 min |
| Spark Windowing (code) | `05-spark-windowing.md` | 7 min | 27 min |
| Order Routing (code) | `06-order-routing.md` | 4 min | 31 min |
| Kill Switch Lifecycle | `07-kill-switch-lifecycle.md` | 3 min | 34 min |
| Live Demo | `08-live-demo.md` | 8-10 min | 42-44 min |
| Exercises | `09-exercises.md` | 2 min | 44-46 min |
| Career + Close | `10-close.md` | 4 min | 48-50 min |

**If running long:** Cut the Kafka deep dive to 2 minutes (they know Kafka basics). Cut the lifecycle section (it's covered in the demo). Skip the global kill in the demo. That saves ~5 minutes.

**If running short:** Expand the demo — show a global kill, trigger panic mode, walk through AKHQ more slowly. Let students ask questions during the demo. Show the compacted topic in detail.
