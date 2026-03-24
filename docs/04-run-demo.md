# Running the Demo

A guided walkthrough of the system using the local Docker Compose stack. Takes about 8-10 minutes from start to finish.

## Before You Start

Make sure the stack is running:

```bash
cd local
docker compose up --build -d
```

Wait about 30 seconds, then verify everything is healthy:

```bash
docker compose ps                    # all containers should show "Up"
curl http://localhost:8000/health     # should return {"status": "healthy"}
docker compose logs order-generator --tail 3  # should show orders being sent
```

Open http://localhost:8080 in your browser — this is AKHQ, the Kafka UI.

---

## Part 1: Normal Operation

Navigate to **Topics** in AKHQ. You should see six topics with message counts climbing in real time. Click into `orders.v1` and open a message. It looks like this:

```json
{
  "order_id": "a1b2c3...",
  "ts": 1710000000000,
  "account_id": "54321",
  "symbol": "AAPL",
  "side": "BUY",
  "qty": 250,
  "price": 178.50,
  "strategy": "ALGO_X"
}
```

Check the order router logs to see what's happening to each order:

```bash
docker compose logs order-router --tail 10
```

Every order should be showing as `ALLOWED`. The order router is checking each order against the kill switch state — and since nothing is killed yet, everything flows through.

---

## Part 2: Triggering the Kill Switch

Kill account 12345:

```bash
curl -X POST http://localhost:8000/kill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"ACCOUNT:12345","reason":"suspicious trading activity"}'
```

The response includes a `cmd_id` and `corr_id` — these are used to trace the command through the system.

**Watch the kill command propagate.** Check the aggregator:

```bash
docker compose logs killswitch-aggregator --tail 5
```

You should see:
```
Processing command: <cmd_id> - ACCOUNT:12345 KILL
State update: ACCOUNT:12345 -> KILLED (reason: suspicious trading activity)
```

**Watch the router enforce it:**

```bash
docker compose logs order-router --tail 10
```

Look for:
```
Kill state update: ACCOUNT:12345 -> KILLED
DROPPED order <id>... account=12345 symbol=AAPL: suspicious trading activity
```

**Check the audit trail in AKHQ.** Open the `audit.v1` topic and find a message with `"decision": "DROP"` for account 12345. Notice the correlation ID, the reason, and the scope match.

The kill command traveled through three separate services — operator console → aggregator → router — in under a second. One API call halted all trading for that account across the entire system. This is what "direct and exclusive control" means under SEC Rule 15c3-5.

---

## Part 3: Recovery

Unkill the account:

```bash
curl -X POST http://localhost:8000/unkill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"ACCOUNT:12345","reason":"cleared after review by compliance team"}'
```

Check the router logs:

```bash
docker compose logs order-router --tail 5
```

You should see:
```
Kill state update: ACCOUNT:12345 -> ACTIVE
```

Orders from account 12345 are flowing again. Notice that the unkill also carries a correlation ID and a reason — the full lifecycle (kill, enforcement, unkill) is auditable.

---

## Part 4: Automatic Detection

The Spark risk detector has been running in the background this entire time. Check the aggregator logs:

```bash
docker compose logs killswitch-aggregator --tail 20
```

You will likely see Spark-triggered kills:
```
State update: ACCOUNT:xxxxx -> KILLED (reason: Symbol concentration breach: 100.0% in NVDA)
```

Spark is consuming every order in 60-second windows. When an account crosses a threshold — too many orders, too much notional value, too concentrated in one symbol — Spark automatically emits a kill command. No human is needed for detection. But a human **is** required for recovery. That's the regulatory requirement: automated surveillance, human oversight of restoration.

The thresholds:

| Metric | Threshold |
|--------|-----------|
| Order rate | > 100 orders / 60s |
| Notional value | > $1M / 60s |
| Symbol concentration | > 70% in a single symbol |

---

## Part 5: The Compacted Topic

In AKHQ, navigate to the `killswitch.state.v1` topic.

This topic uses **log compaction** (`cleanup.policy=compact`). Kafka retains only the latest value per key (the scope). So if ACCOUNT:12345 was killed and then unkilled, only the `ACTIVE` state remains. Any new service starting up can read this topic from the beginning and instantly know the current kill state for every scope.

Compare this to `killswitch.commands.v1`: that topic keeps the full history — every kill and unkill, with timestamps, reasons, and correlation IDs. The commands topic is the audit trail. The state topic is the current truth.

---

## Optional: Additional Scenarios

### Global Kill

```bash
curl -X POST http://localhost:8000/kill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"GLOBAL","reason":"market-wide halt"}'
```

Every order from every account gets dropped. The scope hierarchy is `GLOBAL` > `ACCOUNT:<id>` > `SYMBOL:<symbol>` — the router checks them in order and drops on the first match.

```bash
curl -X POST http://localhost:8000/unkill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"GLOBAL","reason":"market reopened"}'
```

### Exploring the Spark Code

Open `spark/risk_job/risk_detector_local.py` and find the `compute_risk_signals` function:

- `window(event_time, '60 seconds')` — tumbling window from Spark Structured Streaming
- `groupBy(window, account_id)` — windowed aggregation per account
- `detect_threshold_breaches` — where kill commands are emitted

This is the same windowed aggregation pattern from the streaming unit, applied to a real compliance use case.

---

## Cleanup

```bash
cd local
docker compose down -v
```
