# Presentation Guide

A 30-45 minute talk for ITCS 6190/8190 (Cloud Computing for Data Analysis). The audience has already covered Spark, Spark SQL, streaming analytics, and is now learning AWS services. They know what windowing is. They do not need Spark taught from scratch — they need to see it applied to a real problem.

## Before You Start

Start the local stack 10-15 minutes before the presentation:

```bash
cd local
docker compose up --build -d
```

Verify it works:

```bash
curl http://localhost:8000/health
docker compose logs order-router --tail 5
```

Have these ready:
- A terminal with the project directory open
- A browser tab with AKHQ at http://localhost:8080
- This guide open for reference

## Talk Outline

### 1. The Story (5 minutes)

Open with Knight Capital. This is the hook — don't skip it.

**Key points to hit:**
- August 1, 2012. Knight Capital deploys new trading software. An old, dormant piece of code gets accidentally reactivated.
- Within minutes, the system is sending millions of erroneous orders. Buying high, selling low. Across dozens of stocks.
- There is no centralized kill switch. The ops team has to manually log into individual servers to stop them. Some servers get missed.
- 45 minutes. $440 million in losses. More than the company was worth.
- Knight Capital is acquired by Getco at a fraction of its former value six months later.
- The SEC had already passed Rule 15c3-5 (the Market Access Rule) in 2010. Knight's controls were inadequate.

**Why it resonates:** This isn't a theoretical risk. It happened to a real company. People lost their jobs. The company ceased to exist. The fix is engineering — the kind of engineering you're learning to do in this course.

### 2. The Rule (2 minutes)

SEC Rule 15c3-5, in plain English:

- If you're a broker-dealer providing market access, you must have risk controls that prevent clearly erroneous orders from reaching the exchange.
- You must be able to immediately stop all trading from any account (a "kill switch").
- The broker-dealer must have "direct and exclusive control" over these mechanisms — you can't delegate this to the customer or a third party.
- You must maintain records of all controls and their operation.

**One sentence version:** "Before an order touches the market, something must check it. If something goes wrong, you must be able to stop everything immediately. And you must be able to prove you did."

### 3. The Architecture (5 minutes)

Show the architecture diagram (in the README or on a slide). Walk through the data flow:

1. **Orders come in** — the Order Generator produces synthetic orders to `orders.v1`
2. **Two consumers read them** — the Spark Risk Detector and the Order Router
3. **Spark watches for patterns** — computes 60-second windowed aggregations per account
4. **If a threshold is breached** — Spark emits a KILL command to `killswitch.commands.v1`
5. **The Aggregator picks it up** — publishes authoritative state to the compacted `killswitch.state.v1` topic
6. **The Router enforces it** — checks every order against the kill state, allows or drops
7. **Everything is audited** — every routing decision goes to `audit.v1`

**Key architectural principle:** Detection, Control, and Enforcement are separate. Spark detects. The compacted topic controls. The router enforces. This separation means:
- If Spark goes down, the last known kill state is still enforced
- If you need to kill something Spark didn't catch, the operator console can do it directly
- The audit trail captures everything regardless of how the kill was triggered

### 4. Kafka's Role (3 minutes)

Students have seen Kafka in the streaming module. Connect it here:

- **Six topics** — each with a specific purpose (orders, risk signals, commands, state, gated orders, audit)
- **Log compaction** — the `killswitch.state.v1` topic uses `cleanup.policy=compact`. Kafka keeps only the latest value per key (scope). This means any new service that joins can read the entire topic and know the current state of every kill switch instantly.
- **Partitioning** — orders are keyed by `account_id`, so all orders for an account go to the same partition, preserving order.
- **Retention** — commands topic keeps 30 days of history (full audit trail). State topic keeps only the latest per scope.

**The contrast:** Commands topic = "everything that ever happened." State topic = "what's true right now." Both are useful. Both come from the same underlying infrastructure.

### 5. Spark Windowing (5 minutes)

This connects directly to what they learned in weeks 9-10. Show the risk detector code (`spark/risk_job/risk_detector_local.py`):

- **Tumbling windows**: `window(event_time, '60 seconds')` groups orders into non-overlapping 60-second buckets
- **Watermark**: `.withWatermark("event_time", "60 seconds")` tells Spark how late data can arrive before it's dropped
- **Aggregations per window**: `count(*)`, `sum(notional)`, `approx_count_distinct(symbol)` — computed per account per window
- **Symbol concentration**: Uses `collect_list("symbol")` and a UDF to compute what percentage of orders went to the top symbol

**The three thresholds:**

| Metric | Threshold | Real-World Meaning |
|--------|-----------|-------------------|
| Order count > 100/60s | Runaway algorithm | A bot sending orders faster than any human could |
| Notional > $1M/60s | Excessive exposure | Too much money at risk too quickly |
| Top symbol > 70% | Concentration | Hammering one stock — could be a broken algo or manipulation |

**Connect to Knight Capital:** Knight's algorithm was sending orders at a rate that would have tripped all three of these thresholds within seconds. If this system had been in place, the kill switch would have engaged before the losses became catastrophic.

### 6. Why AWS (3 minutes)

Walk through the AWS managed services and why each one matters:

- **MSK Serverless** — Kafka without managing brokers, ZooKeeper, storage, replication. You get the distributed log, AWS handles the rest.
- **EMR Serverless** — Spark without managing clusters. Submit a job, it scales up, runs, scales down. You pay for what you use.
- **Lambda** — each service is a function that runs in response to events. No servers to patch, no capacity to plan.
- **DynamoDB** — fast key-value lookups for the audit trail index. On-demand pricing, no capacity planning.
- **API Gateway** — turns a Lambda function into an HTTP API with one line of Terraform.

**The point:** Every piece of this architecture has a managed service equivalent. You focus on the business logic (detect anomalies, enforce controls, audit decisions). AWS handles the infrastructure (replication, scaling, patching, monitoring).

**Cost context:** This entire system runs for about $5/hour on AWS. That's the cost of a latte. For a system that processes thousands of orders per second with full audit trails and automatic failover.

### 7. Live Demo (8-10 minutes)

See [Demo Script](05-run-demo.md) for the detailed step-by-step. The short version:

1. Show AKHQ — orders flowing through topics
2. Show the operator console health check
3. Show the order router logs — everything is ALLOW
4. Kill an account via curl
5. Show the kill propagate — aggregator logs, router logs switching to DROP
6. Show AKHQ — audit.v1 showing DROP decisions
7. Unkill the account
8. Show orders resume

If time allows, show the Spark auto-kill already happening in the kill switch aggregator logs.

### 8. Close (2 minutes)

**Call to action:**

- The repo is public. Clone it. Run it locally. Break it. Fix it.
- The exercises doc has 10 projects ranging from beginner to advanced — add a symbol-level kill switch, build a dashboard, implement throttling instead of binary kill
- If you're working on your course project, consider how these patterns apply — streaming detection, event-driven responses, audit trails
- These are the tools companies are hiring for. Kafka, Spark, AWS, Terraform, event-driven architecture. Every major bank, every cloud-native company, every data platform team uses some combination of these.

## Timing Summary

| Section | Duration | Running Total |
|---------|----------|---------------|
| Knight Capital story | 5 min | 5 min |
| The rule | 2 min | 7 min |
| Architecture | 5 min | 12 min |
| Kafka's role | 3 min | 15 min |
| Spark windowing | 5 min | 20 min |
| Why AWS | 3 min | 23 min |
| Live demo | 8-10 min | 31-33 min |
| Close + Q&A | 5-12 min | 38-45 min |

## If Things Go Wrong

**Demo fails to start:** Have screenshots or a screen recording of a successful run as backup. The architecture walkthrough and code review carry the talk even without a live demo.

**Spark container crashes:** The rest of the system still works. You can still demo manual kill/unkill via the operator console. Mention that this actually demonstrates the separation of concerns — detection is down, but enforcement is still running.

**Questions you should be ready for:**
- "What happens if Kafka goes down?" — In production, MSK is multi-AZ with replication. Locally, if Kafka dies, everything stops. That's the backbone.
- "Why not just use a database for the kill state?" — You could. Kafka compaction gives you both real-time pub/sub AND durable state in one system. A database would require polling or change data capture.
- "How does this scale?" — MSK scales automatically. EMR scales automatically. Lambda scales automatically. The hard part is the architecture, not the scaling — and the architecture is what we just walked through.
- "Is this real production code?" — No. It's an educational demo. Production systems have additional security, monitoring, disaster recovery, and compliance controls. But the patterns are real.
