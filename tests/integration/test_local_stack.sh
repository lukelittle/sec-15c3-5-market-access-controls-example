#!/bin/bash
# Integration test: Verify local Docker Compose stack works
set -e

echo "=========================================="
echo "Integration Test: Local Stack"
echo "=========================================="
echo ""

cd local

# Test 1: Start services
echo "Test 1: Starting Docker Compose services..."
docker-compose up -d

if [ $? -eq 0 ]; then
  echo "  ✓ Services started"
else
  echo "  ✗ Failed to start services"
  exit 1
fi

# Wait for Kafka to be ready
echo "  Waiting 30 seconds for Kafka to be ready..."
sleep 30

# Test 2: Verify Kafka is running
echo ""
echo "Test 2: Verify Kafka is accessible..."
if docker-compose exec -T kafka kafka-broker-api-versions --bootstrap-server localhost:9092 > /dev/null 2>&1; then
  echo "  ✓ Kafka is accessible"
else
  echo "  ✗ Kafka is not accessible"
  docker-compose logs kafka
  exit 1
fi

# Test 3: Verify topics were created
echo ""
echo "Test 3: Verify topics were created..."
TOPIC_COUNT=$(docker-compose exec -T kafka kafka-topics --bootstrap-server localhost:9092 --list 2>/dev/null | wc -l)

if [ "$TOPIC_COUNT" -ge 6 ]; then
  echo "  ✓ Topics created ($TOPIC_COUNT topics)"
  docker-compose exec -T kafka kafka-topics --bootstrap-server localhost:9092 --list
else
  echo "  ✗ Expected 6+ topics, found $TOPIC_COUNT"
  exit 1
fi

# Test 4: Verify AKHQ UI is accessible
echo ""
echo "Test 4: Verify AKHQ UI is accessible..."
if curl -s http://localhost:8080 > /dev/null; then
  echo "  ✓ AKHQ UI accessible at http://localhost:8080"
else
  echo "  ✗ AKHQ UI not accessible"
  exit 1
fi

# Test 5: Produce test message
echo ""
echo "Test 5: Produce test message to orders.v1..."
echo '{"order_id":"test-123","account_id":"99999","symbol":"TEST","qty":100,"price":50.0}' | \
  docker-compose exec -T kafka kafka-console-producer \
    --bootstrap-server localhost:9092 \
    --topic orders.v1 > /dev/null 2>&1

if [ $? -eq 0 ]; then
  echo "  ✓ Test message produced"
else
  echo "  ✗ Failed to produce message"
  exit 1
fi

# Test 6: Consume test message
echo ""
echo "Test 6: Consume test message from orders.v1..."
MESSAGE=$(timeout 5 docker-compose exec -T kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic orders.v1 \
  --from-beginning \
  --max-messages 1 2>/dev/null || echo "")

if echo "$MESSAGE" | grep -q "test-123"; then
  echo "  ✓ Test message consumed"
else
  echo "  ✗ Failed to consume message"
  exit 1
fi

# Test 7: Verify compacted topic configuration
echo ""
echo "Test 7: Verify killswitch.state.v1 is compacted..."
CLEANUP_POLICY=$(docker-compose exec -T kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --describe \
  --topic killswitch.state.v1 2>/dev/null | grep "cleanup.policy" || echo "")

if echo "$CLEANUP_POLICY" | grep -q "compact"; then
  echo "  ✓ Topic is configured for compaction"
else
  echo "  ⚠ Topic may not be configured for compaction"
  echo "    $CLEANUP_POLICY"
fi

# Summary
echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "✓ Docker Compose services running"
echo "✓ Kafka accessible"
echo "✓ Topics created"
echo "✓ AKHQ UI accessible"
echo "✓ Message production/consumption working"
echo ""
echo "Access AKHQ UI: http://localhost:8080"
echo ""
echo "Stop services with: docker-compose down"
echo ""
echo "✓ Local stack test completed"
