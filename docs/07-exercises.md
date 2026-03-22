# Student Exercises

These exercises build on the demo to deepen understanding of streaming architectures and risk controls.

## Exercise 1: Add Symbol-Level Kill Switch (Beginner)

**Goal**: Implement a kill switch that stops trading for a specific symbol (e.g., "AAPL").

**Tasks**:
1. Modify Spark job to detect symbol concentration breaches
2. Emit KILL command with scope `SYMBOL:AAPL`
3. Update order router to check symbol scope
4. Test by generating high volume for single symbol

**Hints**:
- Symbol scope check goes in `check_kill_status()` function
- Add to scopes list: `f'SYMBOL:{order["symbol"]}'`
- Spark already computes `top_symbol_share`

**Verification**:
```bash
# Trigger high concentration
aws lambda invoke --function-name streaming-risk-dev-order-generator \
  --payload '{"mode": "panic", "symbol": "AAPL", "duration_seconds": 60}' \
  response.json

# Watch for SYMBOL:AAPL kill command
./tools/tail-topic.sh killswitch.commands.v1

# Verify only AAPL orders are dropped
./tools/tail-topic.sh audit.v1 | grep AAPL
```

**Expected outcome**: Orders for AAPL are dropped, other symbols continue.

## Exercise 2: Implement Throttling (Intermediate)

**Goal**: Instead of binary KILL/ALLOW, implement rate limiting (throttling).

**Tasks**:
1. Add new state: `THROTTLED` with `max_rate_per_second`
2. Modify order router to enforce rate limit
3. Add token bucket or sliding window algorithm
4. Update audit trail to show throttled orders

**Design considerations**:
- How do you track rate per account?
- Where do you store token bucket state?
- What happens when rate limit is exceeded?

**State schema**:
```json
{
  "scope": "ACCOUNT:12345",
  "status": "THROTTLED",
  "max_rate_per_second": 10,
  "updated_ts": 1710000000000
}
```

**Verification**:
- Generate 50 orders/sec for account
- Verify only 10/sec pass through
- Check audit trail shows throttled count

## Exercise 3: Add Deduplication (Intermediate)

**Goal**: Prevent duplicate orders with same `order_id` from being processed.

**Tasks**:
1. Add DynamoDB table for seen order IDs
2. Modify order router to check for duplicates
3. Add TTL to expire old order IDs (e.g., 1 hour)
4. Update audit trail with `DUPLICATE` decision

**Hints**:
- Use DynamoDB conditional writes: `attribute_not_exists(order_id)`
- Consider using DynamoDB Streams for async processing
- Think about race conditions

**Verification**:
```bash
# Send same order twice
# First should be ALLOW, second should be DUPLICATE
```

## Exercise 4: Multi-Window Risk Detection (Advanced)

**Goal**: Detect risk across multiple time windows (1min, 5min, 15min).

**Tasks**:
1. Modify Spark job to compute multiple windows
2. Add different thresholds per window
3. Emit risk signals for each window
4. Trigger kill if any window breaches

**Spark SQL**:
```sql
SELECT
    window(event_time, '1 minute') as window_1m,
    window(event_time, '5 minutes') as window_5m,
    window(event_time, '15 minutes') as window_15m,
    account_id,
    COUNT(*) as order_count
FROM orders
GROUP BY ...
```

**Design considerations**:
- How do you avoid duplicate kill commands?
- Which window should take precedence?
- How do you visualize multi-window signals?

## Exercise 5: Automatic Unkill with Cooldown (Advanced)

**Goal**: Automatically unkill after a cooldown period if behavior normalizes.

**Tasks**:
1. Add `cooldown_until` timestamp to kill state
2. Modify Spark job to monitor killed accounts
3. If behavior is normal for N minutes, emit UNKILL
4. Add operator override to prevent auto-unkill

**State schema**:
```json
{
  "scope": "ACCOUNT:12345",
  "status": "KILLED",
  "cooldown_until": 1710000300000,
  "auto_unkill_enabled": true
}
```

**Design considerations**:
- How long should cooldown be?
- What if account misbehaves again immediately?
- Should operator unkills have different cooldown?

## Exercise 6: Real-Time Dashboard (Advanced)

**Goal**: Build a real-time dashboard showing risk signals and kill state.

**Tasks**:
1. Create web frontend (React, Vue, or simple HTML)
2. Backend API to query DynamoDB audit table
3. WebSocket or SSE for real-time updates
4. Visualize: order rate, kill state, dropped orders

**Technologies**:
- Frontend: React + Recharts for graphs
- Backend: API Gateway + Lambda
- Real-time: DynamoDB Streams + Lambda + WebSocket API

**Metrics to show**:
- Current order rate per account
- Kill switch status (color-coded)
- Recent dropped orders
- Risk signal trends

## Exercise 7: Strategy-Level Controls (Intermediate)

**Goal**: Add kill switch for specific trading strategies.

**Tasks**:
1. Add `STRATEGY:<strategy_name>` scope
2. Detect if specific strategy is misbehaving
3. Kill only that strategy, allow others
4. Update audit trail

**Use case**: "ALGO_X is sending erroneous orders, but ALGO_Y is fine"

**Verification**:
```bash
# Generate orders with strategy=ALGO_X
# Trigger kill for STRATEGY:ALGO_X
# Verify ALGO_Y orders still pass
```

## Exercise 8: Latency Optimization (Advanced)

**Goal**: Optimize order router latency to <10ms p99.

**Tasks**:
1. Profile current latency (CloudWatch Insights)
2. Optimize kill state lookup (in-memory cache)
3. Batch audit writes to DynamoDB
4. Use Lambda SnapStart (if applicable)

**Measurement**:
```sql
-- CloudWatch Insights query
fields @timestamp, @duration
| filter @type = "REPORT"
| stats avg(@duration), pct(@duration, 99) by bin(5m)
```

**Optimization techniques**:
- Pre-load kill state into Lambda global scope
- Use DynamoDB batch writes
- Async audit writes (fire-and-forget)
- Connection pooling for Kafka

## Exercise 9: Chaos Engineering (Advanced)

**Goal**: Test system resilience under failure conditions.

**Scenarios**:
1. Kill Spark job mid-stream - does enforcement continue?
2. Partition Kafka - do consumers recover?
3. Throttle Lambda - do orders queue or drop?
4. Corrupt kill state - how do you recover?

**Tools**:
- AWS Fault Injection Simulator
- Manual Lambda throttling
- Kafka partition reassignment

**Expected outcomes**:
- System degrades gracefully
- No orders are incorrectly allowed
- Audit trail remains consistent

## Exercise 10: Regulatory Reporting (Intermediate)

**Goal**: Generate daily regulatory report of all kill switch activations.

**Tasks**:
1. Query audit topic for all KILL commands
2. Aggregate by scope, reason, duration
3. Generate PDF or CSV report
4. Store in S3 with retention policy

**Report format**:
```
Date: 2024-03-15
Total Kill Events: 5
Total Orders Dropped: 1,234

Scope           | Reason              | Duration | Orders Dropped
ACCOUNT:12345   | Order rate breach   | 5 min    | 450
ACCOUNT:67890   | Notional breach     | 2 min    | 180
...
```

**Implementation**:
- Lambda triggered daily by EventBridge
- Query DynamoDB audit table
- Use pandas for aggregation
- Generate report with ReportLab or similar

## Bonus Challenges

### Challenge 1: Multi-Region Deployment
Deploy to multiple AWS regions with cross-region replication.

### Challenge 2: Machine Learning Risk Detection
Replace threshold-based detection with ML model (SageMaker).

### Challenge 3: Blockchain Audit Trail
Store audit trail on blockchain for immutability proof.

### Challenge 4: Compliance Dashboard
Build dashboard showing SEC Rule 15c3-5 compliance metrics.

### Challenge 5: Unit Testing Suite
Add comprehensive unit tests for all Lambda functions:
- Test kill switch logic with pytest
- Mock Kafka producers/consumers
- Test edge cases and error handling
- Achieve >80% code coverage

### Challenge 6: Spark Job Testing
Add tests for Spark streaming job:
- Test windowing logic locally
- Test threshold detection
- Test Kafka integration
- Use PySpark testing framework

### Challenge 7: Integration Test Suite
Expand integration tests:
- Test failure scenarios
- Test recovery procedures
- Test concurrent operations
- Add performance benchmarks

## Submission Guidelines

For each exercise:
1. Document your design decisions
2. Include code changes (pull request or patch)
3. Provide test results and verification
4. Discuss trade-offs and limitations

## Grading Rubric

- **Correctness** (40%): Does it work as specified?
- **Code Quality** (20%): Clean, documented, tested?
- **Design** (20%): Good architectural choices?
- **Testing** (10%): Comprehensive verification?
- **Documentation** (10%): Clear explanation?

## Resources

- [Kafka Documentation](https://kafka.apache.org/documentation/)
- [Spark Structured Streaming Guide](https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html)
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [SEC Rule 15c3-5](https://www.sec.gov/files/rules/final/2010/34-63241.pdf)

## Getting Help

- Review [06-troubleshooting.md](06-troubleshooting.md)
- Check CloudWatch logs
- Use `./tools/tail-topic.sh` to debug
- Ask in class discussion forum
