# Section 4: Kafka Deep Dive — Topics, Compaction, and Schemas

**Duration:** 4 minutes
**Goal:** Explain log compaction as the mechanism that makes distributed kill switch state work.

---

## Opening

> "You've been working with Kafka in this class. Here's how it shows up in a real system. The key concept I want you to walk away with from this section is **log compaction** — because it's what makes the kill switch state work in a distributed system."

---

## The Two Topic Types

> "We have six topics, but they fall into two categories based on how Kafka retains data."

### Time-Retained Topics (5 of 6)

> "Most of our topics use standard time-based retention. `orders.v1` keeps data for 7 days. `audit.v1` keeps data for 90 days. After the retention period, Kafka deletes old segments. These topics are **event logs** — you care about the history."

From `docker-compose.yml` line 49, the topic creator configures these:
```bash
kafka-topics --create --topic orders.v1 --partitions 3 --replication-factor 1
kafka-topics --create --topic audit.v1 --partitions 3 --replication-factor 1
```

Standard retention — Kafka's default behavior.

### The Compacted Topic (1 of 6)

> "But `killswitch.state.v1` is different. It uses `cleanup.policy=compact`."

From `docker-compose.yml` line 49:
```bash
kafka-topics --create --topic killswitch.state.v1 \
  --partitions 3 --replication-factor 1 \
  --config cleanup.policy=compact \
  --config min.cleanable.dirty.ratio=0.01 \
  --config segment.ms=60000
```

> "Log compaction means Kafka keeps **only the latest value per key**. The key for our state topic is the scope — like `GLOBAL`, `ACCOUNT:12345`, or `SYMBOL:AAPL`."

---

## Why Compaction Matters — The Concrete Example

Walk through a concrete scenario. Draw this on a whiteboard if you can.

> "Let's say account 12345 has a busy day:"

```
Offset 1:  key=ACCOUNT:12345  value={"status":"KILLED", "reason":"rate breach"}
Offset 2:  key=ACCOUNT:12345  value={"status":"ACTIVE", "reason":"cleared"}
Offset 3:  key=ACCOUNT:12345  value={"status":"KILLED", "reason":"notional breach"}
Offset 4:  key=ACCOUNT:67890  value={"status":"KILLED", "reason":"concentration"}
Offset 5:  key=ACCOUNT:12345  value={"status":"ACTIVE", "reason":"cleared again"}
```

> "Without compaction, a consumer reading from the beginning sees all 5 messages and has to replay them to figure out the current state."

> "**With** compaction, Kafka periodically removes older records with the same key. After compaction:"

```
Offset 4:  key=ACCOUNT:67890  value={"status":"KILLED", "reason":"concentration"}
Offset 5:  key=ACCOUNT:12345  value={"status":"ACTIVE", "reason":"cleared again"}
```

> "Two records. One per account. The **latest state** for each. A new consumer reading from the beginning immediately knows: account 12345 is ACTIVE, account 67890 is KILLED. No replay needed."

---

## Why This Matters for the Order Router

> "When the Order Router starts up — or restarts after a crash — the first thing it does is read the entire compacted topic from the beginning."

From `route_local.py` lines 57-89, the `load_kill_state()` function:

```python
def load_kill_state():
    """Bootstrap kill state from compacted topic."""
    consumer = KafkaConsumer(
        STATE_TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS.split(','),
        group_id=f'{CONSUMER_GROUP}-bootstrap-{uuid.uuid4().hex[:8]}',
        auto_offset_reset='earliest',      # Read from the beginning
        enable_auto_commit=False,           # Don't commit — this is a one-time read
        consumer_timeout_ms=5000            # Stop after 5s of no new data
    )

    while empty_polls < 3:
        records = consumer.poll(timeout_ms=1000, max_records=100)
        for tp, messages in records.items():
            for message in messages:
                kill_state[message.value['scope']] = message.value

    consumer.close()
```

> "Notice three things about this bootstrap consumer:"

> "**One:** It uses a unique consumer group ID with a random suffix. This ensures it always reads from the beginning, not from where some previous consumer left off."

> "**Two:** `auto_offset_reset='earliest'` means start from offset 0. Combined with compaction, offset 0 of a compacted topic gives you the current state of every key."

> "**Three:** `enable_auto_commit=False`. This consumer doesn't commit offsets because it's throwaway — it reads, loads state into memory, and closes. The main consumer loop uses a different consumer group."

> "After this bootstrap, the router has a Python dictionary mapping every scope to its current state. Checking a kill switch is a dictionary lookup — O(1), microseconds."

---

## Commands vs. State: Two Complementary Topics

> "Here's a design pattern worth remembering: **commands topic for history, state topic for truth.**"

| | `killswitch.commands.v1` | `killswitch.state.v1` |
|---|---|---|
| **Contains** | Every command ever issued | Latest state per scope |
| **Retention** | 30 days (time-based) | Forever (compacted) |
| **Use case** | Audit trail, replay, debugging | Bootstrap, enforcement |
| **Key** | `scope` | `scope` |
| **Growth** | Unbounded within retention | Bounded by number of scopes |

> "If you need to know 'what happened to account 12345 over the last month?' — read the commands topic. If you need to know 'is account 12345 killed right now?' — read the state topic."

> "This is the Event Sourcing pattern. Commands are the events. State is the projection. Kafka gives you both in the same system."

---

## The Compaction Configuration

For the detail-oriented students:

> "Two config values control how aggressively Kafka compacts:"

- `min.cleanable.dirty.ratio=0.01` — compact when even 1% of the log is "dirty" (has superseded records). Default is 0.5. We set it low because we want fresh state fast.
- `segment.ms=60000` — close log segments every 60 seconds. Compaction only operates on closed segments. This means a state change is available to bootstrap consumers within about a minute.

> "In production on MSK, you'd tune these based on your SLA for how fast a new consumer needs to see current state."

---

## Presenter Notes

**The whiteboard example is key.** If you have a whiteboard, draw the before/after compaction. If not, show the slide. The visual of "5 records becomes 2" is what makes compaction click.

**If someone asks "why not just use a database?":** You could. DynamoDB, Redis, Postgres — all work. But then you need two systems: Kafka for events and a database for state. With compaction, Kafka serves both roles. The router doesn't need a database connection, doesn't need to handle database failures, doesn't need database credentials. One system, one protocol, one failure domain.

**If someone asks "what if the compacted topic gets corrupted?":** In production, MSK replicates across availability zones. Locally, if you lose the volume, you lose state — but the commands topic still has the full history. You could rebuild the state topic by replaying commands through the aggregator. That's the beauty of event sourcing: the events are the source of truth, the state is just a cache.

**If someone asks about the `segment.ms` setting:** Active segments are never compacted. `segment.ms=60000` means a new segment is created every minute. The old segment becomes eligible for compaction. So the worst-case delay between a state write and it being available via compaction is about 1-2 minutes. The router's main consumer loop gets updates in real-time via its regular subscription; compaction only matters for bootstrap.

---

## Timing Check

By the end of this section, you should be at **20 minutes** total. You're almost halfway. The next section — Spark windowing — is the technical centerpiece.
