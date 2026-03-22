# Demo Script

Step-by-step instructions for a live demo using the local Docker Compose stack. Takes about 8-10 minutes. Have the stack running before you begin.

## Setup (Before the Demo)

```bash
cd local
docker compose up --build -d
```

Wait about 30 seconds, then verify:

```bash
docker compose ps                    # all containers Up
curl http://localhost:8000/health     # {"status": "healthy"}
docker compose logs order-generator --tail 3  # orders being sent
```

Have these windows ready:
- **Terminal**: the project directory
- **Browser**: AKHQ at http://localhost:8080

## Part 1: Normal Operation (2 minutes)

**Show AKHQ.** Navigate to Topics. Point out the six topics and the message counts climbing.

Click into `orders.v1`. Show a message. Point out the structure:

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

**Show the router logs:**

```bash
docker compose logs order-router --tail 10
```

Point out: all orders are being ALLOWED. The system is running, everything is healthy, the order router is checking every order against the kill switch state and letting them through.

## Part 2: Trigger the Kill Switch (3 minutes)

**Kill an account:**

```bash
curl -X POST http://localhost:8000/kill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"ACCOUNT:12345","reason":"suspicious trading activity"}'
```

Show the response — it includes a `cmd_id` and `corr_id` for tracing.

**Watch it propagate.** Show the aggregator picking it up:

```bash
docker compose logs killswitch-aggregator --tail 5
```

You should see:
```
Processing command: <cmd_id> - ACCOUNT:12345 KILL
State update: ACCOUNT:12345 -> KILLED (reason: suspicious trading activity)
```

**Show the router enforcing it:**

```bash
docker compose logs order-router --tail 10
```

Look for:
```
Kill state update: ACCOUNT:12345 -> KILLED
DROPPED order <id>... account=12345 symbol=AAPL: suspicious trading activity
```

**Show it in AKHQ.** Click on the `audit.v1` topic. Find a message with `"decision": "DROP"` for account 12345. Point out the correlation ID, the reason, and the scope match.

**Key talking point:** The kill command went through three systems (operator console, aggregator, router) in under a second. One curl command stopped all trading for that account across the entire system. That is what "direct and exclusive control" means.

## Part 3: Recovery (2 minutes)

**Unkill the account:**

```bash
curl -X POST http://localhost:8000/unkill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"ACCOUNT:12345","reason":"cleared after review by compliance team"}'
```

**Show the recovery in logs:**

```bash
docker compose logs order-router --tail 5
```

Look for:
```
Kill state update: ACCOUNT:12345 -> ACTIVE
```

Orders from account 12345 are flowing again. Point out: the unkill also has a correlation ID and reason. The full lifecycle — kill, enforcement, unkill — is auditable.

## Part 4: Automatic Detection (2 minutes)

**Show Spark already working.** The risk detector has been running in the background this whole time. Check the aggregator logs:

```bash
docker compose logs killswitch-aggregator --tail 20
```

You will likely see Spark-triggered kills:
```
State update: ACCOUNT:xxxxx -> KILLED (reason: Symbol concentration breach: 100.0% in NVDA)
```

**Explain:** Spark is watching every order in 60-second windows. When an account crosses a threshold — too many orders, too much notional value, too concentrated in one symbol — Spark automatically emits a kill command. No human needed for detection. But a human IS needed for recovery. That's the regulatory requirement.

## Part 5: Show the Compacted Topic (1 minute)

In AKHQ, navigate to the `killswitch.state.v1` topic. Point out:

- This topic uses log compaction (`cleanup.policy=compact`)
- Kafka keeps only the latest value per key (the scope)
- So if ACCOUNT:12345 was killed and then unkilled, only the ACTIVE state remains
- Any new service joining the system can read this topic from the beginning and know the current state of every kill switch instantly

**Contrast with the commands topic:** `killswitch.commands.v1` has the full history — every kill, every unkill, with timestamps and reasons. The commands topic is the audit trail. The state topic is the current truth.

## If You Have Extra Time

### Show a Global Kill

```bash
curl -X POST http://localhost:8000/kill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"GLOBAL","reason":"market-wide halt"}'
```

Every single order gets dropped. Point out the scope hierarchy: GLOBAL overrides everything.

```bash
curl -X POST http://localhost:8000/unkill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"GLOBAL","reason":"market reopened"}'
```

### Show the Code

Open `spark/risk_job/risk_detector_local.py` and show the `compute_risk_signals` function. Point out:
- `window(event_time, '60 seconds')` — they learned this in streaming week
- `groupBy(window, account_id)` — windowed aggregation per account
- The threshold checks in `detect_threshold_breaches`

## Cleanup

After the presentation:

```bash
cd local
docker compose down -v
```
