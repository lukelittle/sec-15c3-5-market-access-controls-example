# Demo Script (10-12 Minutes)

This script is designed for a live classroom presentation. It demonstrates the complete kill switch workflow from normal operation through panic mode, kill trigger, enforcement, and recovery.

## Setup (Before Class)

1. Deploy infrastructure (see [02-deploy-aws.md](02-deploy-aws.md))
2. Start Spark job
3. Have terminal windows ready:
   - Terminal 1: Orders topic
   - Terminal 2: Risk signals topic
   - Terminal 3: Kill commands topic
   - Terminal 4: Audit topic
   - Terminal 5: Commands
4. Open CloudWatch dashboard in browser

## Demo Flow

### Part 1: Architecture Overview (2 minutes)

**Show**: Architecture diagram from README

**Explain**:
- "We're building a real-time risk control system for brokerage order flow"
- "Three key components: Detection (Spark), Control (Kill Switch), Enforcement (Router)"
- "All communication through Kafka topics"
- "This architecture implements patterns required by SEC Rule 15c3-5"

**Key points**:
- Control plane vs data plane separation
- Kafka compacted topic for authoritative state
- Immutable audit trail

### Part 2: Normal Operation (2 minutes)

**Terminal 1** - Start order generator (normal mode):
```bash
aws lambda invoke \
  --function-name streaming-risk-dev-order-generator \
  --payload '{"mode": "normal", "duration_seconds": 600, "rate_per_second": 5}' \
  response.json
```

**Terminal 2** - Watch orders flowing:
```bash
./tools/tail-topic.sh orders.v1
```

**Explain**:
- "Orders are flowing at 5 per second"
- "Each order has account_id, symbol, quantity, price"
- "Router is checking kill switch state and allowing all orders through"

**Terminal 3** - Watch risk signals:
```bash
./tools/tail-topic.sh risk_signals.v1
```

**Explain**:
- "Spark is computing 60-second windows"
- "Tracking order rate, notional value, symbol concentration"
- "All metrics are below thresholds - no alerts"

### Part 3: Trigger Panic Mode (3 minutes)

**Terminal 1** - Trigger panic mode for account 12345:
```bash
aws lambda invoke \
  --function-name streaming-risk-dev-order-generator \
  --payload '{"mode": "panic", "account_id": "12345", "duration_seconds": 120, "rate_per_second": 50}' \
  response.json
```

**Explain**:
- "Simulating a runaway algorithm"
- "Account 12345 suddenly sending 50 orders per second"
- "This is like what happened to Knight Capital in 2012"

**Terminal 3** - Watch risk signals spike:
```bash
# Already tailing risk_signals.v1
# Point out: order_rate_60s jumping to 150+
```

**Explain**:
- "Spark detects order rate breach: 150 orders in 60 seconds"
- "Threshold is 100 orders per 60 seconds"
- "Spark automatically emits a KILL command"

**Terminal 4** - Watch kill command:
```bash
./tools/tail-topic.sh killswitch.commands.v1
```

**Show**:
```json
{
  "cmd_id": "...",
  "scope": "ACCOUNT:12345",
  "action": "KILL",
  "reason": "Order rate breach: 150 orders in 60s",
  "triggered_by": "spark",
  "metric": "order_rate_60s",
  "value": 150
}
```

**Explain**:
- "Kill command published to commands topic"
- "Scope is ACCOUNT:12345 - only this account affected"
- "Includes reason and correlation ID for audit"

### Part 4: Enforcement (2 minutes)

**Terminal 5** - Watch kill state:
```bash
./tools/tail-topic.sh killswitch.state.v1
```

**Show**:
```json
{
  "scope": "ACCOUNT:12345",
  "status": "KILLED",
  "updated_ts": 1710000000000,
  "reason": "Order rate breach: 150 orders in 60s"
}
```

**Explain**:
- "Kill switch aggregator consumed command"
- "Published authoritative state to compacted topic"
- "This is the single source of truth"

**Terminal 6** - Watch audit trail:
```bash
./tools/tail-topic.sh audit.v1
```

**Show**:
```json
{
  "decision": "DROP",
  "order_id": "...",
  "account_id": "12345",
  "reason": "Kill switch active for ACCOUNT:12345",
  "corr_id": "..."
}
```

**Explain**:
- "Order router is now dropping all orders from account 12345"
- "Other accounts continue to trade normally"
- "Every decision is audited with correlation ID"

**CloudWatch Dashboard**:
- Show dropped order count increasing
- Show Lambda invocations

### Part 5: Manual Recovery (2 minutes)

**Terminal 1** - Manual unkill via operator console:
```bash
curl -X POST $API_URL/unkill \
  -H "Content-Type: application/json" \
  -d '{
    "scope": "ACCOUNT:12345",
    "reason": "Manual override after investigation",
    "operator": "demo_operator"
  }'
```

**Explain**:
- "Operator investigates and determines it's safe to resume"
- "Sends UNKILL command via API"
- "This demonstrates 'direct and exclusive control'"

**Terminal 5** - Watch state update:
```bash
# Still tailing killswitch.state.v1
# Show status changing to ACTIVE
```

**Terminal 6** - Watch orders resume:
```bash
# Tail audit.v1
# Show decision changing to ALLOW
```

**Explain**:
- "Orders from account 12345 are now allowed again"
- "Full audit trail of kill -> unkill -> resume"
- "Correlation IDs link the entire sequence"

### Part 6: Kafka Compaction Demo (1 minute)

**Terminal 1** - Show compaction:
```bash
kafka-topics --bootstrap-server $MSK_BOOTSTRAP \
  --describe --topic killswitch.state.v1
```

**Explain**:
- "State topic is configured with cleanup.policy=compact"
- "Kafka retains only latest value per scope"
- "New consumers can bootstrap current state quickly"
- "Commands topic retains full history"

**Show diagram**:
```
Commands Topic (all history):
ACCOUNT:12345 -> KILL   (t=100)
ACCOUNT:12345 -> UNKILL (t=200)

State Topic (compacted, latest only):
ACCOUNT:12345 -> ACTIVE (t=200)
```

## Key Takeaways

**Summarize**:
1. **Real-time detection**: Spark SQL windows detect anomalies in seconds
2. **Centralized control**: Single source of truth for kill state
3. **Consistent enforcement**: Every order checked, every decision audited
4. **Regulatory compliance**: Implements "direct and exclusive control"
5. **Operational patterns**: Compaction, correlation IDs, separation of concerns

**Connect to Knight Capital**:
- "Knight Capital lacked this centralized kill mechanism"
- "No way to stop all servers simultaneously"
- "Lost $440M in 45 minutes"
- "This architecture prevents that failure mode"

**Connect to SEC Rule 15c3-5**:
- "Rule requires 'direct and exclusive control'"
- "Must prevent erroneous orders"
- "Must maintain audit trail"
- "This demo implements those requirements"

## Q&A Topics

Be prepared to discuss:
- Why separate detection from enforcement?
- Why use Kafka compaction instead of database?
- How does this scale to millions of orders per second?
- What happens if Spark job fails?
- How do you test kill switch in production?
- What other scopes could you add? (SYMBOL, STRATEGY, etc.)

## Cleanup

After demo:
```bash
cd terraform/envs/dev
terraform destroy
```

## Variations

### Shorter Demo (5 minutes)
- Skip normal operation
- Start directly with panic mode
- Focus on kill trigger and enforcement

### Longer Demo (20 minutes)
- Add SYMBOL-level kill switch
- Show multiple concurrent accounts
- Demonstrate throttling vs binary kill
- Show DynamoDB audit queries

### Interactive Demo
- Let students trigger panic mode
- Have students write unkill commands
- Students modify thresholds and redeploy

## Common Issues

### Orders not flowing
- Check Lambda logs: `aws logs tail /aws/lambda/streaming-risk-dev-order-generator --follow`
- Verify MSK cluster is healthy
- Check VPC security groups

### Kill switch not triggering
- Verify Spark job is running: `aws emr-serverless list-job-runs --application-id $EMR_APP_ID`
- Check thresholds are set correctly
- Increase panic mode rate if needed

### Audit trail not showing
- Check order router Lambda is running
- Verify audit topic exists
- Check CloudWatch logs for errors

## Next Steps

After demo:
- [05-exercises.md](05-exercises.md): Student exercises
- [04-observe.md](04-observe.md): Deep dive on observability
- [06-troubleshooting.md](06-troubleshooting.md): Common issues
