# Section 8: Live Demo

**Duration:** 8-10 minutes
**Goal:** Show the running system — normal operation, manual kill, recovery, and automatic detection. Every command is exact and copy-pasteable.

---

## Pre-Demo Checklist

You should have started the stack 15 minutes before class. Verify now:

```bash
cd local
docker compose ps
```

All containers should show `Up`. If any are `Exited` or `Restarting`, fix before proceeding:

```bash
# If something crashed, rebuild
docker compose up --build -d

# Quick health check
curl http://localhost:8000/health
# Expected: {"service":"operator-console","status":"healthy"}

docker compose logs order-generator --tail 3
# Expected: "Sent 100 orders..." lines
```

Have two windows ready:
1. **Terminal** — for curl commands and log tailing
2. **Browser** — AKHQ at http://localhost:8080

---

## Demo Part 1: Normal Operation (2 minutes)

### Show AKHQ

Open http://localhost:8080 in the browser. Click **Topics** in the left sidebar.

> "Here are all six topics. You can see the message counts climbing — orders are flowing through the system in real time."

Click into **`orders.v1`**. Click on a message to expand it.

> "Each order has an ID, a timestamp, an account, a symbol, a side — buy or sell — a quantity, a price, and a strategy. This is the raw input to the system."

Point out the message count and throughput:

> "We're generating about 5 orders per second. In production, this would be thousands or tens of thousands per second."

### Show Router Logs

Switch to terminal:

```bash
docker compose logs order-router --tail 10
```

> "Everything is ALLOW. The system is healthy. Every order is passing through the router, getting checked against the kill state, and being forwarded to the gated topic."

Expected output:
```
Processed 500 orders (allowed: 500, dropped: 0)
Processed 600 orders (allowed: 600, dropped: 0)
```

> "Zero drops. That's normal operation."

---

## Demo Part 2: Manual Kill Switch (3 minutes)

This is the dramatic moment. Build it up.

> "Now let's see what happens when something goes wrong. I'm going to kill account 12345."

### Trigger the Kill

```bash
curl -X POST http://localhost:8000/kill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"ACCOUNT:12345","reason":"suspicious trading activity"}'
```

Expected response:
```json
{
  "cmd_id": "abc-...",
  "command": {
    "action": "KILL",
    "scope": "ACCOUNT:12345",
    "reason": "suspicious trading activity",
    "triggered_by": "api"
  },
  "corr_id": "def-...",
  "success": true
}
```

> "One curl command. That's it. I just killed account 12345. Let's watch it propagate."

### Show Propagation

```bash
docker compose logs killswitch-aggregator --tail 5
```

> "The aggregator received the command and updated the state. Look: 'State update: ACCOUNT:12345 -> KILLED'."

```bash
docker compose logs order-router --tail 15
```

> "And now the router is dropping orders from account 12345. See the DROPPED lines? But orders from other accounts — 67890, 54321 — are still flowing. The kill is scoped."

Expected output:
```
Kill state update: ACCOUNT:12345 -> KILLED
DROPPED order abc123... account=12345 symbol=AAPL: suspicious trading activity
DROPPED order def456... account=12345 symbol=GOOGL: suspicious trading activity
Processed 700 orders (allowed: 685, dropped: 15)
```

### Show the Audit Trail

Go back to AKHQ. Click into **`audit.v1`**. Find a recent message with `decision: DROP`.

> "Every decision is audited. This record shows: decision was DROP, the account, the symbol, the reason, and a correlation ID that traces back to the kill command. If a regulator asks 'why did you drop this order at 2:15 PM?' — this is the answer."

### The Key Point

Pause and address the class directly:

> "One curl command stopped all trading for that account across the entire system in under a second. That's what 'direct and exclusive control' means. That's what Knight Capital didn't have."

---

## Demo Part 3: Recovery (2 minutes)

> "Now let's clear the kill and restore trading."

### Unkill the Account

```bash
curl -X POST http://localhost:8000/unkill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"ACCOUNT:12345","reason":"cleared after review"}'
```

### Verify Recovery

```bash
docker compose logs order-router --tail 10
```

> "Account 12345 is active again. Orders are flowing. And the unkill is also audited — you can trace the full lifecycle from kill to unkill."

Expected output:
```
Kill state update: ACCOUNT:12345 -> ACTIVE
Processed 800 orders (allowed: 800, dropped: 0)
```

### Show Global Kill (Optional — If You Have Time)

> "Let me show you the nuclear option."

```bash
curl -X POST http://localhost:8000/kill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"GLOBAL","reason":"market emergency"}'
```

```bash
docker compose logs order-router --tail 10
```

> "Every order from every account is now dropped. This is GLOBAL scope. In a real market emergency — a flash crash, a system-wide failure — one command stops everything."

Unkill immediately so you don't lose demo time:

```bash
curl -X POST http://localhost:8000/unkill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"GLOBAL","reason":"emergency resolved"}'
```

---

## Demo Part 4: Automatic Detection by Spark (2 minutes)

> "Everything I just showed you was manual — a human pressing a button. But Spark has been running in the background this whole time, watching every order."

### Check for Spark-Triggered Kills

```bash
docker compose logs killswitch-aggregator --tail 30
```

Look for lines where `triggered_by` is `spark`:

> "Look — Spark has already detected some accounts with threshold breaches and auto-killed them. See: 'Symbol concentration breach: 85% in AAPL.' No human involved in the detection."

If Spark hasn't triggered any kills yet (thresholds are calibrated for the normal rate), trigger panic mode:

```bash
# Stop the normal generator
docker compose stop order-generator

# Start a panic generator that sends 50 orders/sec concentrated on few symbols
docker compose run -d --name panic-generator \
  -e MODE=panic \
  -e RATE_PER_SECOND=50 \
  -e KAFKA_BOOTSTRAP_SERVERS=kafka:29092 \
  order-generator python -u generate_local.py
```

Wait about 60-90 seconds (one window cycle), then:

```bash
docker compose logs killswitch-aggregator --tail 10
```

> "There — Spark detected the anomalous trading pattern and issued a kill command automatically. The aggregator processed it. The router is now dropping orders from that account."

Clean up:

```bash
docker stop panic-generator && docker rm panic-generator
docker compose start order-generator
```

---

## Demo Part 5: The Compacted Topic (1 minute, if time permits)

In AKHQ, navigate to **`killswitch.state.v1`**.

> "This is the compacted topic. Notice: there's one record per scope. Even though we issued multiple kill and unkill commands during this demo, the topic only shows the latest state for each scope."

> "If I started a brand-new service right now and told it to read this topic from the beginning, it would immediately know the current state of every kill switch. That's the power of compaction."

Compare with **`killswitch.commands.v1`**:

> "Contrast that with the commands topic — every command we issued is here. This is the full history. The state topic is truth-now. The commands topic is truth-over-time."

---

## If Things Go Wrong During the Demo

**Order generator stopped producing:**
```bash
docker compose restart order-generator
# Wait 5 seconds, then check
docker compose logs order-generator --tail 3
```

**Spark container crashed:**
> "Actually, this is a great demo moment. Spark is down, but watch — the kill state is still enforced. The router is still checking the compacted topic. Detection stopped, but enforcement continues. That's the separation of concerns we talked about."
```bash
docker compose restart spark-risk-detector
```

**Kafka is unhealthy:**
```bash
docker compose restart kafka
# Wait 30 seconds for Kafka to stabilize
docker compose restart order-generator killswitch-aggregator order-router operator-console spark-risk-detector
```

**Nothing works and you're panicking:**
Fall back to the code walkthrough. The architecture slides and code carry the talk even without a live demo.

> "The demo is having a bad day — which, honestly, is exactly what this system is designed to handle. Let me show you the code instead."

---

## Timing Check

By the end of the demo, you should be at **42-44 minutes** total. You have a few minutes left for exercises and the close.
