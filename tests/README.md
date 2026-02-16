# Testing Guide

This directory contains tests for the streaming risk controls demo.

## Test Philosophy

This is an **educational demo**, not production software. Tests are designed to:
- ✅ Verify the system works end-to-end
- ✅ Help students understand system behavior
- ✅ Provide examples for student exercises
- ❌ Not achieve 100% code coverage
- ❌ Not test every edge case

## Test Types

### Integration Tests (Provided)

Test the deployed system end-to-end:

```bash
# Test AWS deployment
cd tests/integration
./test_demo_flow.sh

# Test local Docker Compose
./test_local_stack.sh
```

**What they test:**
- Order generation works
- Kafka topics are accessible
- Messages flow through the system
- Kill switch triggers correctly
- Audit trail is created

**Prerequisites:**
- AWS deployment (for test_demo_flow.sh)
- Docker Compose (for test_local_stack.sh)
- kcat installed (optional, for message verification)

### Unit Tests (Student Exercise)

**Not provided** - Students can add these as exercises:

```python
# Example: tests/unit/test_order_router.py
def test_global_kill_blocks_all_orders():
    """Test that GLOBAL kill blocks orders from any account"""
    # Student implements this
    pass
```

See [docs/05-exercises.md](../docs/05-exercises.md) for unit testing exercises.

### Spark Tests (Advanced Exercise)

**Not provided** - Advanced students can add these:

```python
# Example: tests/spark/test_risk_detector.py
def test_windowed_aggregation(spark):
    """Test that 60-second windows aggregate correctly"""
    # Student implements this
    pass
```

## Running Tests

### Integration Tests

**AWS Deployment Test:**
```bash
# 1. Deploy infrastructure
cd terraform/envs/dev
terraform apply

# 2. Set environment variables
export MSK_BOOTSTRAP=$(terraform output -raw msk_bootstrap_brokers)
export AWS_REGION=us-east-1

# 3. Run test
cd ../../..
./tests/integration/test_demo_flow.sh
```

**Expected output:**
```
==========================================
Integration Test: Demo Flow
==========================================

Test 1: Generate normal orders (30 seconds)...
  ✓ Order generator invoked successfully
  Waiting 10 seconds for orders to flow...

Test 2: Verify orders in orders.v1 topic...
  ✓ Orders flowing (150 messages)

Test 3: Trigger panic mode (account 12345, 60 seconds)...
  ✓ Panic mode triggered
  Waiting 45 seconds for Spark to detect breach...

Test 4: Verify kill command in killswitch.commands.v1...
  ✓ Kill command emitted (1 commands)

Test 5: Verify kill state in killswitch.state.v1...
  ✓ Kill state updated (1 states)

Test 6: Verify dropped orders in audit.v1...
  ✓ Orders being dropped (234 dropped)

Test 7: Verify DynamoDB audit index...
  ✓ Audit records in DynamoDB (384 items)

==========================================
Test Summary
==========================================
✓ Order generation working
✓ Kafka topics accessible
✓ End-to-end flow verified

✓ Integration test completed
```

**Local Stack Test:**
```bash
cd local
../tests/integration/test_local_stack.sh
```

**Expected output:**
```
==========================================
Integration Test: Local Stack
==========================================

Test 1: Starting Docker Compose services...
  ✓ Services started
  Waiting 30 seconds for Kafka to be ready...

Test 2: Verify Kafka is accessible...
  ✓ Kafka is accessible

Test 3: Verify topics were created...
  ✓ Topics created (6 topics)

Test 4: Verify AKHQ UI is accessible...
  ✓ AKHQ UI accessible at http://localhost:8080

Test 5: Produce test message to orders.v1...
  ✓ Test message produced

Test 6: Consume test message from orders.v1...
  ✓ Test message consumed

Test 7: Verify killswitch.state.v1 is compacted...
  ✓ Topic is configured for compaction

==========================================
Test Summary
==========================================
✓ Docker Compose services running
✓ Kafka accessible
✓ Topics created
✓ AKHQ UI accessible
✓ Message production/consumption working

✓ Local stack test completed
```

## Troubleshooting Tests

### Test fails: "MSK_BOOTSTRAP environment variable not set"

**Solution:**
```bash
cd terraform/envs/dev
export MSK_BOOTSTRAP=$(terraform output -raw msk_bootstrap_brokers)
```

### Test fails: "kcat not found"

**Solution:**
```bash
# macOS
brew install kcat

# Linux
sudo apt-get install kafkacat  # kcat was formerly kafkacat
```

The test will continue without kcat, but message verification will be skipped.

### Test fails: "No kill command found"

**Possible causes:**
1. Spark job not running
2. Threshold not breached
3. Spark still processing

**Solution:**
```bash
# Check Spark job status
aws emr-serverless list-job-runs --application-id $EMR_APP_ID

# Check Spark logs
aws s3 ls s3://$S3_BUCKET/spark-logs/

# Increase panic mode duration
# Edit test script: "duration_seconds": 120
```

### Test fails: "Kafka is not accessible"

**Solution:**
```bash
# Check Docker Compose logs
cd local
docker-compose logs kafka

# Restart services
docker-compose down
docker-compose up -d
```

## Writing Your Own Tests

### Example: Unit Test for Kill Switch Logic

```python
# tests/unit/test_kill_switch.py
import pytest
from services.order_router.handler import check_kill_status

def test_account_kill_scope():
    """Test that ACCOUNT scope only affects that account"""
    kill_state = {
        'ACCOUNT:12345': {
            'status': 'KILLED',
            'reason': 'Risk breach'
        }
    }
    
    # Test killed account
    order1 = {'account_id': '12345', 'symbol': 'AAPL'}
    should_kill, scopes, reason = check_kill_status(order1, kill_state)
    assert should_kill == True
    assert 'ACCOUNT:12345' in scopes
    
    # Test different account (should pass)
    order2 = {'account_id': '67890', 'symbol': 'AAPL'}
    should_kill, scopes, reason = check_kill_status(order2, kill_state)
    assert should_kill == False

# Run with: pytest tests/unit/
```

### Example: Spark Test

```python
# tests/spark/test_windowing.py
from pyspark.sql import SparkSession
from pyspark.sql.functions import window, count
import pytest

@pytest.fixture
def spark():
    return SparkSession.builder \
        .master("local[2]") \
        .appName("test") \
        .getOrCreate()

def test_60_second_window(spark):
    """Test that 60-second windows aggregate correctly"""
    from pyspark.sql.types import StructType, StructField, StringType, TimestampType
    
    schema = StructType([
        StructField("account_id", StringType()),
        StructField("event_time", TimestampType())
    ])
    
    data = [
        ("12345", "2024-01-01 10:00:00"),
        ("12345", "2024-01-01 10:00:30"),
        ("12345", "2024-01-01 10:01:30"),  # Next window
    ]
    
    df = spark.createDataFrame(data, schema)
    
    result = df.groupBy(
        window("event_time", "60 seconds"),
        "account_id"
    ).agg(count("*").alias("count"))
    
    windows = result.collect()
    assert len(windows) == 2  # Two windows
    assert windows[0]["count"] == 2  # First window

# Run with: pytest tests/spark/
```

## Test Coverage

Current test coverage:

| Component | Integration | Unit | Spark |
|-----------|-------------|------|-------|
| Order Generator | ✓ | - | - |
| Kill Switch Aggregator | ✓ | - | - |
| Order Router | ✓ | - | - |
| Operator Console | - | - | - |
| Spark Risk Detector | ✓ | - | - |
| Kafka Topics | ✓ | - | - |
| DynamoDB | ✓ | - | - |

**Legend:**
- ✓ = Tested
- - = Not tested (can be student exercise)

## Student Exercises

See [docs/05-exercises.md](../docs/05-exercises.md) for testing exercises:

- **Exercise 12**: Add unit tests for order router
- **Exercise 13**: Add Spark job tests
- **Exercise 14**: Add API integration tests
- **Exercise 15**: Add chaos engineering tests

## Best Practices

1. **Keep tests simple** - This is educational, not production
2. **Test behavior, not implementation** - Focus on what the system does
3. **Use real services when possible** - Integration tests are more valuable
4. **Document test assumptions** - Help students understand what's being tested
5. **Make tests runnable** - Students should be able to run tests easily

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [PySpark testing guide](https://spark.apache.org/docs/latest/api/python/getting_started/testing_pyspark.html)
- [Kafka testing strategies](https://kafka.apache.org/documentation/#testing)
- [AWS Lambda testing](https://docs.aws.amazon.com/lambda/latest/dg/testing-functions.html)
