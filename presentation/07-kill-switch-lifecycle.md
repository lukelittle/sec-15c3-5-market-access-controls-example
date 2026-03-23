# Section 7: Kill Switch Lifecycle — Aggregator and Operator Console

**Duration:** 3 minutes
**Goal:** Show how commands flow through the aggregator to become state, and how the operator console gives humans control.

---

## Opening

> "We've seen how Spark detects and how the router enforces. Now let's look at the two components in between: the aggregator that manages state, and the operator console that gives humans a button to push."

---

## The Kill Switch Aggregator

**File:** `services/killswitch_aggregator/aggregate_local.py` (120 lines)

### The Core Logic: `process_command()` (Lines 56-88)

```python
def process_command(command, producer):
    scope = command['scope']
    action = command['action']

    if action == 'KILL':
        status = 'KILLED'
    elif action == 'UNKILL':
        status = 'ACTIVE'
    else:
        print(f"Unknown action: {action}")
        return

    state = {
        'scope': scope,
        'status': status,
        'updated_ts': int(time.time() * 1000),
        'updated_by': command.get('triggered_by', 'unknown'),
        'reason': command.get('reason', ''),
        'last_cmd_id': command['cmd_id'],
        'corr_id': command.get('corr_id', str(uuid.uuid4()))
    }

    future = producer.send(STATE_TOPIC, key=scope, value=state)
    future.get(timeout=10)  # Synchronous — wait for Kafka ack
```

> "The aggregator is deliberately simple. It does exactly one thing: translate a command into state."

> "KILL action becomes KILLED status. UNKILL action becomes ACTIVE status. That's it. The state record carries forward the correlation ID, the timestamp, who triggered it, and the reason."

> "**Two things to notice:**"

> "**One:** `producer.send(...).get(timeout=10)` — this is a **synchronous** write. The aggregator waits for Kafka to acknowledge the write before processing the next command. In most Kafka producers you'd use fire-and-forget for throughput. Here, we wait. Why? Because this is the kill switch. If the write fails, we need to know immediately, not discover it later. Correctness over throughput."

> "**Two:** The Kafka key is `scope` — like `ACCOUNT:12345`. Because the state topic is compacted by key, this means each scope has exactly one authoritative state record. Write a KILL, then write an UNKILL — after compaction, only the UNKILL remains. That's the latest truth."

### Why a Separate Aggregator?

> "You might ask: why not have Spark or the operator console write directly to the state topic? Why an intermediary?"

> "Answer: **single writer principle.** Only the aggregator writes to the state topic. This means you can add validation, rate limiting, deduplication, or conflict resolution in one place. If two kill commands arrive for the same scope at the same time — maybe Spark and an operator both react to the same event — the aggregator processes them in order. No race conditions, no split-brain."

---

## The Operator Console

**File:** `services/operator_console/api_local.py` (106 lines)

### Scope Validation (Lines 56-61)

```python
def validate_scope(scope):
    if not scope:
        return False, 'Missing required field: scope'
    if not (scope == 'GLOBAL' or
            scope.startswith('ACCOUNT:') or
            scope.startswith('SYMBOL:')):
        return False, 'Invalid scope format. Use GLOBAL, ACCOUNT:<id>, or SYMBOL:<symbol>'
    return True, None
```

> "Before publishing any command, the console validates the scope format. Only three patterns are accepted: `GLOBAL`, `ACCOUNT:<id>`, or `SYMBOL:<symbol>`. Anything else is rejected with a 400 error."

> "This is input validation at the boundary. The aggregator trusts that commands have valid scopes because the console enforces it."

### The Kill Endpoint (Lines 69-83)

```python
@app.route('/kill', methods=['POST'])
def kill():
    body = request.get_json(force=True, silent=True) or {}
    scope = body.get('scope')
    reason = body.get('reason', 'Manual operator action')
    operator = body.get('operator', 'api')

    valid, error = validate_scope(scope)
    if not valid:
        return jsonify({'error': error}), 400

    result = publish_command('KILL', scope, reason, operator)
    if result['success']:
        return jsonify(result)
    return jsonify(result), 500
```

> "POST /kill with a JSON body: `scope` and `reason`. The console generates a unique `cmd_id` and `corr_id`, publishes the command to `killswitch.commands.v1`, and returns the IDs to the caller."

> "The response includes the `cmd_id` and `corr_id`, so the operator can trace their action through the system. 'I killed account 12345 at 2:15 PM, command ID abc-123, and I can look that up in the audit trail.'"

### The Command Publishing (Lines 29-53)

```python
def publish_command(action, scope, reason, operator='api'):
    cmd_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    command = {
        'cmd_id': cmd_id,
        'ts': int(time.time() * 1000),
        'scope': scope,
        'action': action,
        'reason': reason,
        'triggered_by': operator,
        'corr_id': corr_id
    }

    producer = get_producer()
    future = producer.send(COMMANDS_TOPIC, key=scope, value=command)
    future.get(timeout=10)
```

> "Same pattern as the aggregator — synchronous write with `future.get()`. When you POST /kill, you don't get a response until Kafka has acknowledged the command. If Kafka is down, you get a 500 error, not a false success."

---

## The Full Lifecycle

Walk through the complete path of a kill-and-recovery cycle:

> "Let's trace one complete lifecycle:"

```
1. Spark detects: account 12345 sent 150 orders in 60 seconds
2. Spark emits:   KILL command → killswitch.commands.v1
                  {scope: "ACCOUNT:12345", action: "KILL",
                   triggered_by: "spark", reason: "Order rate breach: 150 orders in 60s"}

3. Aggregator reads command, writes state → killswitch.state.v1
                  {scope: "ACCOUNT:12345", status: "KILLED", ...}

4. Router reads state update, updates in-memory dict
5. Next order from account 12345 → DROPPED, audit event written

   ... time passes, operator investigates ...

6. Operator calls: POST /kill with scope=ACCOUNT:12345 → wait, it's already killed
   Actually: POST /unkill
                  {scope: "ACCOUNT:12345", action: "UNKILL",
                   triggered_by: "api", reason: "cleared after review"}

7. Aggregator reads command, writes state → killswitch.state.v1
                  {scope: "ACCOUNT:12345", status: "ACTIVE", ...}

8. Router reads state update, updates in-memory dict
9. Next order from account 12345 → ALLOWED, forwarded to orders.gated.v1
```

> "**Automatic detection, manual recovery.** The machine pulls the brake. Only a human releases it. Every step is audited with correlation IDs."

---

## Presenter Notes

**Keep this section brisk.** The aggregator and console are straightforward code. The audience should get the lifecycle concept more than the implementation details.

**If someone asks "why Flask?":** It's simple, everyone knows it, and it's fine for a demo. In production, you'd use something behind an API Gateway with authentication. The console has no auth — that's intentional for the demo but noted in the security docs.

**If someone asks "what if the aggregator processes commands out of order?":** Kafka preserves order within a partition. The commands topic uses `scope` as the key, so all commands for the same scope land on the same partition and are processed in order. A KILL followed by an UNKILL for the same scope will always be processed in that order.

---

## Timing Check

By the end of this section, you should be at **34 minutes** total. You're in the home stretch — the live demo is next.
