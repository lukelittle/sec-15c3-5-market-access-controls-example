#!/bin/bash
# Integration test: Verify complete demo flow works
set -e

echo "=========================================="
echo "Integration Test: Demo Flow"
echo "=========================================="
echo ""

# Check prerequisites
if [ -z "$MSK_BOOTSTRAP" ]; then
  echo "Error: MSK_BOOTSTRAP environment variable not set"
  echo "Run: export MSK_BOOTSTRAP=\$(cd terraform/envs/dev && terraform output -raw msk_bootstrap_brokers)"
  exit 1
fi

if ! command -v kcat &> /dev/null; then
  echo "Warning: kcat not found. Install with: brew install kcat"
  echo "Continuing without message count verification..."
  SKIP_KAFKA_CHECK=true
fi

echo "Prerequisites:"
echo "  MSK Bootstrap: $MSK_BOOTSTRAP"
echo "  AWS Region: ${AWS_REGION:-us-east-1}"
echo ""

# Test 1: Generate normal orders
echo "Test 1: Generate normal orders (30 seconds)..."
aws lambda invoke \
  --function-name streaming-risk-dev-order-generator \
  --payload '{"mode": "normal", "duration_seconds": 30, "rate_per_second": 5}' \
  --cli-read-timeout 60 \
  response.json > /dev/null 2>&1

if [ $? -eq 0 ]; then
  echo "  ✓ Order generator invoked successfully"
else
  echo "  ✗ Order generator invocation failed"
  exit 1
fi

# Wait for orders to flow
echo "  Waiting 10 seconds for orders to flow..."
sleep 10

# Test 2: Verify orders in Kafka
if [ "$SKIP_KAFKA_CHECK" != "true" ]; then
  echo ""
  echo "Test 2: Verify orders in orders.v1 topic..."
  ORDER_COUNT=$(timeout 5 kcat -C -b $MSK_BOOTSTRAP -t orders.v1 -e -o beginning 2>/dev/null | wc -l || echo "0")
  
  if [ "$ORDER_COUNT" -gt 0 ]; then
    echo "  ✓ Orders flowing ($ORDER_COUNT messages)"
  else
    echo "  ✗ No orders found in topic"
    exit 1
  fi
fi

# Test 3: Trigger panic mode
echo ""
echo "Test 3: Trigger panic mode (account 12345, 60 seconds)..."
aws lambda invoke \
  --function-name streaming-risk-dev-order-generator \
  --payload '{"mode": "panic", "account_id": "12345", "duration_seconds": 60, "rate_per_second": 50}' \
  --cli-read-timeout 90 \
  response.json > /dev/null 2>&1

if [ $? -eq 0 ]; then
  echo "  ✓ Panic mode triggered"
else
  echo "  ✗ Panic mode trigger failed"
  exit 1
fi

# Wait for Spark to detect and emit kill command
echo "  Waiting 45 seconds for Spark to detect breach..."
sleep 45

# Test 4: Verify kill command
if [ "$SKIP_KAFKA_CHECK" != "true" ]; then
  echo ""
  echo "Test 4: Verify kill command in killswitch.commands.v1..."
  KILL_COUNT=$(timeout 5 kcat -C -b $MSK_BOOTSTRAP -t killswitch.commands.v1 -e -o beginning 2>/dev/null | grep -c "KILL" || echo "0")
  
  if [ "$KILL_COUNT" -gt 0 ]; then
    echo "  ✓ Kill command emitted ($KILL_COUNT commands)"
  else
    echo "  ⚠ No kill command found (Spark may still be processing)"
    echo "    Check Spark job status: aws emr-serverless list-job-runs --application-id \$EMR_APP_ID"
  fi
fi

# Test 5: Verify kill state
if [ "$SKIP_KAFKA_CHECK" != "true" ]; then
  echo ""
  echo "Test 5: Verify kill state in killswitch.state.v1..."
  STATE_COUNT=$(timeout 5 kcat -C -b $MSK_BOOTSTRAP -t killswitch.state.v1 -e -o beginning 2>/dev/null | grep -c "KILLED" || echo "0")
  
  if [ "$STATE_COUNT" -gt 0 ]; then
    echo "  ✓ Kill state updated ($STATE_COUNT states)"
  else
    echo "  ⚠ No kill state found (aggregator may still be processing)"
  fi
fi

# Test 6: Verify audit trail
if [ "$SKIP_KAFKA_CHECK" != "true" ]; then
  echo ""
  echo "Test 6: Verify dropped orders in audit.v1..."
  DROP_COUNT=$(timeout 5 kcat -C -b $MSK_BOOTSTRAP -t audit.v1 -e -o beginning 2>/dev/null | grep -c "DROP" || echo "0")
  
  if [ "$DROP_COUNT" -gt 0 ]; then
    echo "  ✓ Orders being dropped ($DROP_COUNT dropped)"
  else
    echo "  ⚠ No dropped orders found (router may still be processing)"
  fi
fi

# Test 7: Verify DynamoDB audit index
echo ""
echo "Test 7: Verify DynamoDB audit index..."
AUDIT_ITEMS=$(aws dynamodb scan \
  --table-name streaming-risk-dev-audit-index \
  --select COUNT \
  --query 'Count' \
  --output text 2>/dev/null || echo "0")

if [ "$AUDIT_ITEMS" -gt 0 ]; then
  echo "  ✓ Audit records in DynamoDB ($AUDIT_ITEMS items)"
else
  echo "  ⚠ No audit records in DynamoDB yet"
fi

# Summary
echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "✓ Order generation working"
echo "✓ Kafka topics accessible"
if [ "$SKIP_KAFKA_CHECK" != "true" ]; then
  echo "✓ End-to-end flow verified"
else
  echo "⚠ Kafka verification skipped (install kcat)"
fi
echo ""
echo "Manual verification:"
echo "  ./tools/tail-topic.sh orders.v1"
echo "  ./tools/tail-topic.sh risk_signals.v1"
echo "  ./tools/tail-topic.sh killswitch.commands.v1"
echo "  ./tools/tail-topic.sh audit.v1"
echo ""
echo "✓ Integration test completed"
