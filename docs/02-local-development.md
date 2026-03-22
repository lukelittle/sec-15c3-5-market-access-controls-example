# Local Development

Run the entire system on your laptop with Docker Compose. No AWS account, no cloud costs.

## What You Get

| Service | Container | Port |
|---------|-----------|------|
| Kafka (KRaft mode) | `kafka` | 9092 (host), 29092 (internal) |
| Kafka UI (AKHQ) | `akhq` | 8080 |
| Order Generator | `order-generator` | -- |
| Kill Switch Aggregator | `killswitch-aggregator` | -- |
| Order Router | `order-router` | -- |
| Operator Console | `operator-console` | 8000 |
| Spark Risk Detector | `spark-risk-detector` | -- |
| Topic Creator | `topic-creator` | (exits after creating topics) |

## Prerequisites

- Docker and Docker Compose
- `curl` (for testing the API)
- About 4 GB of free RAM

## Starting the Stack

```bash
cd local
docker compose up --build -d
```

First run takes a few minutes to pull images and build containers. Subsequent starts are fast.

## Verifying Everything Works

```bash
# All containers should show "Up" (topic-creator will show "Exited (0)")
docker compose ps

# Health check
curl http://localhost:8000/health

# Orders should be flowing — check the logs
docker compose logs order-generator --tail 5
docker compose logs order-router --tail 5
```

Open http://localhost:8080 in your browser to see AKHQ. Click on "Topics" to see all six Kafka topics and the messages flowing through them.

## Testing the Kill Switch

### Manual Kill

```bash
# Kill account 12345
curl -X POST http://localhost:8000/kill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"ACCOUNT:12345","reason":"suspicious activity"}'

# Watch the router start dropping orders for that account
docker compose logs order-router --tail 20

# Check AKHQ: audit.v1 topic will show DROP decisions
```

### Manual Unkill

```bash
curl -X POST http://localhost:8000/unkill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"ACCOUNT:12345","reason":"cleared after review"}'
```

### Global Kill (Emergency)

```bash
curl -X POST http://localhost:8000/kill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"GLOBAL","reason":"market halt"}'
```

This blocks ALL orders from ALL accounts until explicitly unkilled.

### Symbol-Level Kill

```bash
curl -X POST http://localhost:8000/kill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"SYMBOL:AAPL","reason":"halted pending news"}'
```

## Spark Auto-Detection

The Spark risk detector runs continuously, watching for:

| Metric | Threshold | What It Means |
|--------|-----------|---------------|
| Order rate | > 100 orders/60s | Account is sending orders too fast |
| Notional value | > $1M/60s | Account is pushing too much dollar exposure |
| Symbol concentration | > 70% | Account is hammering a single symbol |

When any threshold is breached, Spark automatically emits a KILL command. You will see this in the logs:

```bash
docker compose logs killswitch-aggregator --tail 20
# Look for: "State update: ACCOUNT:xxxxx -> KILLED (reason: Symbol concentration breach...)"
```

## Switching to Panic Mode

To trigger a breach intentionally (useful for demos):

```bash
# Stop the current generator
docker compose stop order-generator

# Restart it in panic mode
docker compose run -d --name order-generator-panic \
  -e MODE=panic \
  -e ACCOUNT_ID=12345 \
  -e RATE_PER_SECOND=50 \
  -e DURATION_SECONDS=60 \
  order-generator
```

Or edit the `MODE` environment variable in `docker-compose.yml` and restart:

```bash
docker compose up -d order-generator
```

## Viewing Kafka Topics in AKHQ

Open http://localhost:8080 and navigate to Topics. Key topics to watch:

- **orders.v1** — raw order stream (high volume)
- **killswitch.commands.v1** — kill/unkill commands (low volume, interesting)
- **killswitch.state.v1** — current state per scope (compacted)
- **audit.v1** — every routing decision (ALLOW/DROP)
- **risk_signals.v1** — windowed risk metrics from Spark
- **orders.gated.v1** — orders that passed the kill switch check

## Stopping and Cleaning Up

```bash
# Stop everything
docker compose down

# Stop and remove all data (including Kafka topics)
docker compose down -v
```

## Local vs AWS

The local stack runs the same business logic as the AWS deployment. The differences:

| Aspect | Local | AWS |
|--------|-------|-----|
| Kafka | Single-node Docker (KRaft) | MSK Serverless (multi-AZ) |
| Spark | Single-node (local[2]) | EMR Serverless (clustered) |
| Services | Python processes | Lambda functions |
| State cache | In-memory dicts | DynamoDB |
| API | Flask on port 8000 | API Gateway + Lambda |
| Auth | None (PLAINTEXT) | IAM (SASL_SSL + SigV4) |
| Cost | $0 | $4-6/hour |
| Scale | Demo only | Production-capable |

## Troubleshooting

**Containers won't start**: Make sure Docker has at least 4 GB of RAM allocated.

**Spark container keeps restarting**: Check logs with `docker compose logs spark-risk-detector`. On first run, it needs to download the Kafka connector JAR — this is baked into the image so it should be fast.

**Orders not flowing**: The services wait for the `topic-creator` container to finish before starting. Check that it exited successfully: `docker compose ps topic-creator`.

**Port conflict on 8080 or 8000**: Another service is using that port. Either stop it or change the port mapping in `docker-compose.yml`.
