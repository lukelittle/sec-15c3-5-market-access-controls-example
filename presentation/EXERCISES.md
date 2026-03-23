# Student Exercises

All exercises run locally with Docker Compose. No AWS account needed.

## Getting Started

```bash
git clone https://github.com/lukelittle/sec-15c3-5-market-access-controls-example.git
cd sec-15c3-5-market-access-controls-example/local
docker compose up --build -d
```

Verify it's running:
```bash
curl http://localhost:8000/health
docker compose logs order-router --tail 5
```

AKHQ (Kafka UI) is at http://localhost:8080. Use it to inspect topics and messages.

---

## Exercise 1: Add Symbol-Level Kill Switch (Beginner)

**Goal:** Kill trading for a specific stock symbol, not just an account.

Right now you can kill by `ACCOUNT:12345` or `GLOBAL`. Add `SYMBOL:AAPL` support.

**What to modify:**
- `services/order_router/route_local.py` — add `SYMBOL:{symbol}` to the scopes checked in `check_kill_status()`
- Test it:

```bash
# Kill all AAPL trading
curl -X POST http://localhost:8000/kill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"SYMBOL:AAPL","reason":"halted pending news"}'

# Check that AAPL orders are dropped but GOOGL orders pass
docker compose logs order-router --tail 20

# Unkill it
curl -X POST http://localhost:8000/unkill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"SYMBOL:AAPL","reason":"trading resumed"}'
```

**Hint:** The `check_kill_status()` function already checks `GLOBAL` and `ACCOUNT:*`. Add one more scope to the list.

---

## Exercise 2: Implement Throttling (Intermediate)

**Goal:** Instead of binary KILL/ALLOW, add a THROTTLED state that rate-limits orders.

**Design:**
- New state: `{"status": "THROTTLED", "max_rate_per_second": 10}`
- Router allows up to N orders per second from the account, drops the rest
- Audit trail shows `THROTTLED` decision

**What to modify:**
- `services/order_router/route_local.py` — add throttle logic with an in-memory counter per account
- `services/operator_console/api_local.py` — add a `POST /throttle` endpoint

**Test:**
```bash
curl -X POST http://localhost:8000/throttle \
  -H 'Content-Type: application/json' \
  -d '{"scope":"ACCOUNT:12345","max_rate":10,"reason":"rate limiting"}'
```

**Think about:** Where do you store the counter? What happens when the minute rolls over? Is this fair to the account?

---

## Exercise 3: Multi-Window Detection (Intermediate)

**Goal:** Detect risk across 1-minute AND 5-minute windows simultaneously.

Right now Spark uses a single 60-second window. Add a 5-minute window with different thresholds.

**What to modify:**
- `spark/risk_job/risk_detector_local.py` — add a second aggregation with `window(event_time, '5 minutes')`
- Different thresholds: maybe 100 orders/1min but 300 orders/5min
- Both windows should emit to `killswitch.commands.v1` on breach

**Rebuild after changes:**
```bash
docker compose up --build -d spark-risk-detector
```

**Think about:** What if both windows trigger a kill for the same account? How do you avoid duplicate kill commands?

---

## Exercise 4: Automatic Unkill with Cooldown (Intermediate)

**Goal:** After a kill, automatically unkill if behavior normalizes for 5 minutes.

**Design:**
- When Spark kills an account, start a cooldown timer
- If no new breaches detected for 5 minutes, emit an UNKILL
- Operator kills should NOT auto-unkill (manual kills require manual recovery)

**What to modify:**
- `spark/risk_job/risk_detector_local.py` — track killed accounts, check if they've been quiet
- The kill command from Spark has `"triggered_by": "spark"` — use that to distinguish from operator kills

**Think about:** What if the account misbehaves again 30 seconds after auto-unkill? Should there be a backoff?

---

## Exercise 5: Add Strategy-Level Controls (Beginner)

**Goal:** Kill a specific trading strategy across all accounts.

Each order has a `strategy` field (ALGO_X, ALGO_Y, MANUAL, SMART_ROUTER). Add the ability to kill a strategy.

```bash
curl -X POST http://localhost:8000/kill \
  -H 'Content-Type: application/json' \
  -d '{"scope":"STRATEGY:ALGO_X","reason":"algorithm misbehaving"}'
```

**What to modify:**
- `services/order_router/route_local.py` — add `STRATEGY:{strategy}` to scope checks
- `services/operator_console/api_local.py` — update scope validation to accept STRATEGY

---

## Exercise 6: Real-Time Dashboard (Advanced)

**Goal:** Build a web page that shows live order rates and kill switch state.

**Approach:**
- Read from Kafka topics using a Python consumer
- Serve a web page with Flask or FastAPI
- Use Server-Sent Events (SSE) or polling for live updates
- Show: orders/second, active kills, recent DROP decisions

**Starting point:** The operator console (`api_local.py`) already has Flask. Add routes for:
- `GET /status` — return current kill state (read from killswitch.state.v1)
- `GET /metrics` — return order counts from the last minute

**Bonus:** Add a simple HTML page with charts using Chart.js.

---

## Exercise 7: Deduplication (Intermediate)

**Goal:** Prevent the same order from being processed twice.

**What to build:**
- In the order router, keep a set of recently seen `order_id` values
- If a duplicate arrives, drop it with decision `DUPLICATE`
- Expire old IDs after 1 hour (don't let the set grow forever)

**What to modify:**
- `services/order_router/route_local.py` — add a dedup check before the kill switch check

**Think about:** What data structure? A set works for small volumes. What about at scale? (Bloom filters, Redis, DynamoDB)

---

## Exercise 8: Regulatory Report Generator (Intermediate)

**Goal:** Generate a daily report of all kill switch activations.

**What to build:**
- A Python script that reads from `killswitch.commands.v1` (use kafka-python consumer)
- Aggregate: how many kills, by scope, by reason, duration until unkill
- Output a CSV or formatted text report

**Run it:**
```bash
docker compose exec order-router python -c "
from kafka import KafkaConsumer
import json
consumer = KafkaConsumer('killswitch.commands.v1',
    bootstrap_servers='kafka:29092',
    value_deserializer=lambda v: json.loads(v.decode()),
    auto_offset_reset='earliest',
    consumer_timeout_ms=5000)
for msg in consumer:
    print(f'{msg.value[\"scope\"]:20s} {msg.value[\"action\"]:8s} {msg.value[\"reason\"]}')
"
```

---

## Exercise 9: Chaos Testing (Advanced)

**Goal:** Test what happens when parts of the system fail.

**Scenarios to try:**

1. **Kill the Spark container:**
```bash
docker compose stop spark-risk-detector
# Does enforcement still work? (It should — kill state is already in the compacted topic)
# Test: manually kill and unkill via operator console
docker compose start spark-risk-detector
```

2. **Kill the aggregator:**
```bash
docker compose stop killswitch-aggregator
# What happens to kill commands? (They queue in Kafka)
docker compose start killswitch-aggregator
# Do queued commands get processed? (They should)
```

3. **Restart Kafka:**
```bash
docker compose restart kafka
# What recovers? What doesn't? How long does it take?
```

**Document:** What failed, what recovered automatically, what needed manual intervention.

---

## Exercise 10: Add Unit Tests (Beginner)

**Goal:** Write tests for the core business logic.

The kill switch check logic in `route_local.py` is pure Python — no Kafka dependency for the `check_kill_status()` function.

**Write tests:**
```python
# test_killswitch.py
from route_local import check_kill_status, kill_state

def test_no_kill_state():
    kill_state.clear()
    order = {"account_id": "12345", "symbol": "AAPL"}
    should_kill, scopes, reason = check_kill_status(order)
    assert should_kill == False

def test_account_killed():
    kill_state["ACCOUNT:12345"] = {"status": "KILLED", "reason": "test"}
    order = {"account_id": "12345", "symbol": "AAPL"}
    should_kill, scopes, reason = check_kill_status(order)
    assert should_kill == True

def test_global_kill():
    kill_state["GLOBAL"] = {"status": "KILLED", "reason": "market halt"}
    order = {"account_id": "99999", "symbol": "GOOGL"}
    should_kill, scopes, reason = check_kill_status(order)
    assert should_kill == True
```

Run:
```bash
pip install pytest
pytest test_killswitch.py -v
```

---

## Submission

For each exercise:
1. Fork the repo
2. Create a branch: `exercise-N-yourname`
3. Make your changes
4. Test locally with Docker Compose
5. Write a brief README in your branch explaining what you did and how to test it
6. Submit the branch URL

---

## Resources

- [Kafka Documentation](https://kafka.apache.org/documentation/)
- [Spark Structured Streaming Guide](https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [SEC Rule 15c3-5 Full Text](https://www.sec.gov/files/rules/final/2010/34-63241.pdf)
- [Knight Capital Incident SEC Report](https://www.sec.gov/litigation/admin/2013/34-70694.pdf)
