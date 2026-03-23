# Section 6: Order Routing — The Enforcement Layer

**Duration:** 4 minutes
**Goal:** Walk through `services/order_router/route_local.py` to show how kill switch state is enforced on every order.

**File:** `services/order_router/route_local.py` (202 lines)

---

## Opening

> "Spark detects. The compacted topic holds state. But nothing actually stops an order until the **Order Router** says 'no.' Let's look at how enforcement works."

---

## The Core Function: `check_kill_status()` (Lines 92-110)

This is the most important function in the entire system. It's what stands between an order and the market.

```python
def check_kill_status(order):
    account_id = order['account_id']
    symbol = order['symbol']

    scopes_to_check = [
        'GLOBAL',
        f'ACCOUNT:{account_id}',
        f'SYMBOL:{symbol}'
    ]

    matched_scopes = []
    for scope in scopes_to_check:
        if scope in kill_state:
            state = kill_state[scope]
            matched_scopes.append(scope)
            if state['status'] == 'KILLED':
                return True, matched_scopes, state.get('reason', 'Kill switch active')

    return False, matched_scopes, None
```

> "For every single order, this function checks three scopes in priority order:"

> "**First: GLOBAL.** Is there a global kill switch active? If yes, every order from every account is dropped. This is the nuclear option — something has gone so wrong that all trading must stop."

> "**Second: ACCOUNT:{account_id}.** Is this specific account killed? If yes, all orders from this account are dropped, but other accounts can trade normally. This is what Spark triggers when it detects a rate breach."

> "**Third: SYMBOL:{symbol}.** Is trading halted for this specific stock? If yes, no one can trade this symbol, regardless of account. This is for market-wide halts — like when a stock is suspended pending news."

> "The order of the list matters. GLOBAL is checked first because it overrides everything. If there's a global kill, we don't need to check account or symbol — everything stops."

> "**Implementation detail:** `kill_state` is a Python dictionary. This lookup is O(1) per scope, O(3) per order. At 5 orders per second, this adds microseconds. At 5,000 orders per second in production, it's still trivially fast."

---

## The Routing Decision: `route_order()` (Lines 113-146)

```python
def route_order(order, producer):
    should_kill, matched_scopes, reason = check_kill_status(order)
    corr_id = str(uuid.uuid4())

    if should_kill:
        decision = 'DROP'
        print(f"DROPPED order {order['order_id'][:8]}... "
              f"account={order['account_id']} symbol={order['symbol']}: {reason}")
    else:
        decision = 'ALLOW'
        producer.send(GATED_TOPIC, key=order['account_id'], value=order)

    audit_event = {
        'ts': int(time.time() * 1000),
        'decision': decision,
        'order_id': order['order_id'],
        'account_id': order['account_id'],
        'symbol': order['symbol'],
        'scope_matches': matched_scopes,
        'killswitch_status': 'KILLED' if should_kill else 'ACTIVE',
        'reason': reason or 'No kill switch active',
        'corr_id': corr_id,
        'service': 'order_router'
    }

    producer.send(AUDIT_TOPIC, key=order['order_id'], value=audit_event)
    return audit_event
```

> "Two paths, every time:"

> "**DROP path:** The order is killed. It is **not** forwarded to `orders.gated.v1`. It simply disappears. The only trace is the audit event. This is the safety guarantee — a killed order never reaches the market."

> "**ALLOW path:** The order is forwarded to `orders.gated.v1` — the 'gated' topic represents orders that have passed the pre-trade check and are approved for market delivery."

> "**In both cases:** An audit event is written to `audit.v1`. Every order, whether allowed or dropped, gets a record with: the decision, the timestamp, which scopes matched, the reason, and a correlation ID. This is the audit trail the SEC requires."

> "Notice the `corr_id`. This is a new UUID generated for each routing decision. It connects this audit event to the kill command that caused it. If a regulator asks 'why was this order dropped?' — you follow the `corr_id` to the kill command, which has its own `corr_id` linking to the Spark detection or operator action."

---

## State Bootstrap: `load_kill_state()` (Lines 57-89)

> "When the router starts up, it doesn't know any kill state. It needs to bootstrap from the compacted topic."

```python
def load_kill_state():
    consumer = KafkaConsumer(
        STATE_TOPIC,
        group_id=f'{CONSUMER_GROUP}-bootstrap-{uuid.uuid4().hex[:8]}',
        auto_offset_reset='earliest',
        enable_auto_commit=False,
        consumer_timeout_ms=5000
    )

    while empty_polls < 3:
        records = consumer.poll(timeout_ms=1000, max_records=100)
        for tp, messages in records.items():
            for message in messages:
                kill_state[message.value['scope']] = message.value

    consumer.close()
    print(f"Loaded {state_count} state records, {len(kill_state)} unique scopes")
```

> "Three key design choices here:"

> "**Unique consumer group:** Each bootstrap gets a random group ID. This ensures we always read from offset 0, not from where a previous bootstrap stopped."

> "**Three empty polls to stop:** We poll Kafka in a loop. When we get three consecutive empty poll results (3 seconds of no new data), we assume we've read everything and stop. This handles the case where the compacted topic might have data spread across multiple partitions."

> "**Dictionary assignment, not append:** `kill_state[scope] = message.value` overwrites any previous value for the same scope. Since the topic is compacted, there should be at most one record per scope, but this makes the code resilient to races during compaction."

---

## The Main Loop: Dual-Topic Consumer (Lines 149-197)

```python
def main():
    load_kill_state()                                    # Bootstrap first
    consumer = create_consumer([ORDERS_TOPIC, STATE_TOPIC])  # Then subscribe to both

    while running:
        records = consumer.poll(timeout_ms=1000, max_records=100)
        for tp, messages in records.items():
            for message in messages:
                if message.topic == STATE_TOPIC:         # State update
                    kill_state[scope] = state
                    print(f"Kill state update: {scope} -> {state['status']}")
                    continue

                order = message.value                    # Order to route
                audit_event = route_order(order, producer)
```

> "After bootstrap, the main loop subscribes to **both** `orders.v1` and `killswitch.state.v1`. This is critical — it means the router gets real-time state updates without a second consumer."

> "When a state update arrives, it updates the in-memory dictionary. When an order arrives, it routes it against the current state. The check is always against the latest known state."

> "**Race condition question:** What if a kill command and an order arrive at the same time? Could an order slip through? In practice, Kafka's consumer poll returns messages in offset order per partition. State updates propagate within one poll cycle (1 second max). For the sub-second gap, yes, an order could theoretically slip through. In production, you'd add a confirmation step at the exchange level. But for the purposes of this system, the latency is acceptable."

---

## Presenter Notes

**Key takeaway for the audience:** The router is intentionally simple. Check state, make decision, audit it. No complex logic, no ML, no heuristics. Simple code means fewer bugs. In a safety-critical system, simplicity is a feature.

**If someone asks "why not check against a database?":** Latency. A DynamoDB read takes 1-5ms. A dictionary lookup takes microseconds. At high order volumes, this matters. The dictionary is populated from Kafka, which is the source of truth.

**If someone asks "what if the router crashes mid-order?":** The order is in Kafka, which is durable. When the router restarts, it bootstraps state and resumes consuming from where it left off (committed offsets). The same order will be processed again. Since routing decisions are deterministic (same state = same decision), replaying is safe. This is **exactly once semantics** for the routing decision, achieved through Kafka's consumer group offset management.

---

## Timing Check

By the end of this section, you should be at **31 minutes** total.
