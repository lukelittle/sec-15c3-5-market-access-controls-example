# Section 9: Hands-On Exercises

**Duration:** 2 minutes in the talk (overview only). Students do these on their own time.
**Goal:** Give students concrete, runnable exercises that require actual code changes, tested via Docker Compose.

---

## How to Present This Section

> "The repo has 10 exercises if you want to go deeper. I'm going to highlight three that connect directly to what we covered today. All of them run locally with Docker Compose — no AWS account, no cost."

Pick 2-3 exercises based on the audience. For a Spark-heavy class, lead with Exercise 3. For a systems class, lead with Exercise 1.

---

## Exercise 1: Symbol-Level Kill Switch (Beginner, ~30 min)

**What they learn:** How the scope hierarchy works, modifying a safety-critical code path.

**The problem:** The router already checks `SYMBOL:{symbol}` in `check_kill_status()` (line 99 of `route_local.py`), but the operator console's `validate_scope()` function (line 56 of `api_local.py`) already accepts `SYMBOL:` prefix. This exercise is really about **verifying** the existing implementation and **testing** it end-to-end.

**What to actually do:**

1. Start the stack:
```bash
cd local
docker compose up --build -d
```

2. Kill a specific symbol:
```bash
curl -X POST http://localhost:8000/kill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"SYMBOL:AAPL","reason":"halted pending news"}'
```

3. Verify only AAPL orders are dropped:
```bash
# Watch the router logs — AAPL should be DROPPED, others ALLOWED
docker compose logs -f order-router 2>&1 | grep -E "DROPPED|ALLOW.*AAPL"
```

4. Verify in AKHQ — check `audit.v1` for DROP decisions with `symbol: AAPL`.

5. Unkill and verify recovery:
```bash
curl -X POST http://localhost:8000/unkill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"SYMBOL:AAPL","reason":"trading resumed"}'
```

**Extension challenge:** Add a `STRATEGY:` scope so you can kill a specific algorithm (ALGO_X, ALGO_Y, etc.) across all accounts. This requires changes to:
- `route_local.py` line 96-100: add `f'STRATEGY:{order["strategy"]}'` to `scopes_to_check`
- `api_local.py` line 59: add `scope.startswith('STRATEGY:')` to the validation

Then test:
```bash
curl -X POST http://localhost:8000/kill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"STRATEGY:ALGO_X","reason":"algorithm misbehaving"}'

# Check that ALGO_X orders are dropped regardless of account
docker compose logs order-router --tail 20
```

Rebuild after code changes:
```bash
docker compose up --build -d order-router
```

---

## Exercise 3: Multi-Window Detection (Intermediate, ~1 hour)

**What they learn:** Spark windowing, running multiple aggregations, handling duplicate kill commands.

**The problem:** The risk detector uses a single 60-second tumbling window. Some anomalies are only visible over longer time periods. Add a 5-minute window with different thresholds.

**What to actually change in `spark/risk_job/risk_detector_local.py`:**

1. Add a second aggregation function after `compute_risk_signals()`:

```python
def compute_risk_signals_5min(orders_df):
    """5-minute tumbling windows with higher thresholds."""
    return orders_df \
        .withWatermark("event_time", "5 minutes") \
        .groupBy(
            window(col("event_time"), "5 minutes"),
            col("account_id")
        ) \
        .agg(
            count("*").alias("order_count"),
            spark_sum("notional").alias("total_notional"),
            avg("notional").alias("avg_notional"),
            approx_count_distinct("symbol").alias("unique_symbols"),
            spark_max("symbol").alias("top_symbol"),
            collect_list("symbol").alias("_symbols")
        ) \
        .withColumn("window_start", col("window.start")) \
        .withColumn("window_end", col("window.end")) \
        .withColumn("ts", (unix_timestamp(current_timestamp()) * lit(1000)).cast("long")) \
        .withColumn("top_symbol_share", compute_concentration(col("_symbols"))) \
        .drop("window", "_symbols")
```

2. Add higher thresholds for the 5-minute window:

```python
# At the top of the file, add:
ORDER_RATE_THRESHOLD_5MIN = 300      # 300 orders in 5 minutes
NOTIONAL_THRESHOLD_5MIN = 3000000    # $3M in 5 minutes
```

3. Create a separate breach detection for the 5-minute window (copy `detect_threshold_breaches` with the new thresholds).

4. In `main()`, add the second pipeline:

```python
def main():
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    orders_df = read_orders_stream(spark)

    # 1-minute window (existing)
    risk_signals_1min = compute_risk_signals(orders_df)
    kill_commands_1min = detect_threshold_breaches(risk_signals_1min)

    # 5-minute window (new)
    risk_signals_5min = compute_risk_signals_5min(orders_df)
    kill_commands_5min = detect_threshold_breaches_5min(risk_signals_5min)

    # Start all queries
    write_risk_signals(risk_signals_1min)
    write_kill_commands(kill_commands_1min)

    # Need separate checkpoint locations for 5-min queries
    risk_signals_5min \
        .select(col("account_id").alias("key"), to_json(struct("*")).alias("value")) \
        .writeStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("topic", "risk_signals.v1") \
        .option("checkpointLocation", "/tmp/checkpoint/risk_signals_5min") \
        .outputMode("update") \
        .start()

    kill_commands_5min \
        .select(col("scope").alias("key"), to_json(struct("*")).alias("value")) \
        .writeStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("topic", "killswitch.commands.v1") \
        .option("checkpointLocation", "/tmp/checkpoint/kill_commands_5min") \
        .outputMode("append") \
        .start()
```

5. Rebuild and test:
```bash
docker compose up --build -d spark-risk-detector
# Wait 5+ minutes, then check for 5-minute window detections
docker compose logs killswitch-aggregator --tail 20
```

**Think about (discussion questions):**
- If both the 1-minute and 5-minute windows trigger a kill for the same account, what happens? (Answer: two KILL commands arrive at the aggregator. The second one overwrites the first in the state topic, but both are recorded in the commands topic. No harm — killing an already-killed account is a no-op at the router level.)
- Should the reason message distinguish which window triggered the kill? (Yes — add "5min:" prefix to the reason string so operators know which detection triggered.)

---

## Exercise 9: Chaos Testing (Advanced, ~1 hour)

**What they learn:** How distributed systems behave under failure, the value of the separation-of-concerns architecture.

**Scenario 1: Kill Spark**

```bash
# Stop Spark
docker compose stop spark-risk-detector

# Verify enforcement still works
curl -X POST http://localhost:8000/kill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"ACCOUNT:12345","reason":"manual test during Spark outage"}'

docker compose logs order-router --tail 10
# Expected: DROPPED for account 12345. Enforcement works without Spark.

curl -X POST http://localhost:8000/unkill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"ACCOUNT:12345","reason":"test complete"}'

# Restart Spark
docker compose start spark-risk-detector
# Spark picks up from its checkpoint. No data loss.
```

**What to document:** Detection stopped but enforcement continued. The compacted topic held the state. This proves the separation of detection and enforcement.

**Scenario 2: Kill the Aggregator**

```bash
# Stop the aggregator
docker compose stop killswitch-aggregator

# Issue a kill command
curl -X POST http://localhost:8000/kill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"ACCOUNT:67890","reason":"test during aggregator outage"}'

# The curl succeeds! The command is written to Kafka.
# But the state topic is NOT updated. The router doesn't know about the kill.

docker compose logs order-router --tail 5
# Expected: still ALLOW for account 67890 — the router hasn't seen a state update

# Restart the aggregator
docker compose start killswitch-aggregator

# Wait a few seconds...
docker compose logs killswitch-aggregator --tail 5
# Expected: "Processing command... ACCOUNT:67890 KILL"
# The queued command gets processed!

docker compose logs order-router --tail 5
# Expected: now DROPPING account 67890
```

**What to document:** Commands queued in Kafka while the aggregator was down. When it came back, it consumed from its last committed offset and processed the queued commands. This is Kafka's durability guarantee in action.

**Scenario 3: Restart Kafka**

```bash
docker compose restart kafka

# Watch what happens to each service
docker compose logs order-generator --tail 5    # Reconnects or errors?
docker compose logs order-router --tail 5       # Reconnects? State preserved?
docker compose logs killswitch-aggregator --tail 5
docker compose logs spark-risk-detector --tail 10  # Spark is the most fragile

# If Spark lost its streaming queries, restart it:
docker compose restart spark-risk-detector
```

**What to document:** Which services recovered automatically? Which needed a manual restart? How long did recovery take? Did the kill state survive the restart? (Answer: yes, because the compacted topic is on Kafka's disk volume, which is a Docker volume that survives container restarts.)

**Write-up template:**

| Scenario | What Broke | What Still Worked | Recovery Method | Time to Recover |
|----------|-----------|-------------------|-----------------|-----------------|
| Spark down | Auto-detection | Manual kill/unkill, enforcement | `docker compose start spark-risk-detector` | ~30s |
| Aggregator down | State updates | Existing kills enforced, commands queue in Kafka | `docker compose start killswitch-aggregator` | ~5s |
| Kafka restart | Everything briefly | Nothing (Kafka is the backbone) | Automatic reconnection for most services | ~30-60s |

---

## Quick Reference: Rebuild Commands

After modifying any service code:

```bash
# Rebuild a single service
docker compose up --build -d <service-name>

# Rebuild everything
docker compose up --build -d

# View logs for a specific service
docker compose logs -f <service-name>

# Service names:
#   order-generator
#   killswitch-aggregator
#   order-router
#   operator-console
#   spark-risk-detector
```

---

## All 10 Exercises (Summary for the Slide)

| # | Exercise | Difficulty | Primary File(s) |
|---|----------|-----------|-----------------|
| 1 | Symbol-level kill switch | Beginner | `route_local.py`, `api_local.py` |
| 2 | Throttling (rate-limited state) | Intermediate | `route_local.py`, `api_local.py` |
| 3 | Multi-window detection | Intermediate | `risk_detector_local.py` |
| 4 | Auto-unkill with cooldown | Intermediate | `risk_detector_local.py` |
| 5 | Strategy-level controls | Beginner | `route_local.py`, `api_local.py` |
| 6 | Real-time dashboard | Advanced | New service |
| 7 | Order deduplication | Intermediate | `route_local.py` |
| 8 | Regulatory report generator | Intermediate | New script |
| 9 | Chaos testing | Advanced | Docker Compose operations |
| 10 | Unit tests | Beginner | New test file |

Full descriptions are in `presentation/EXERCISES.md`.

---

## Presenter Notes

**In the talk, spend no more than 2 minutes on this.** Just show the slide with the exercise list, highlight 2-3, and move on. The detailed instructions above are for students working on their own.

**Which exercises to highlight depends on the audience:**
- Spark-focused class: Exercises 3 (multi-window) and 4 (auto-unkill)
- Systems/architecture class: Exercises 1 (scopes) and 9 (chaos)
- Software engineering class: Exercises 2 (throttling) and 10 (unit tests)
