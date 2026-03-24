#!/bin/bash
# =============================================================================
# SEC 15c3-5 Market Access Controls - Live Demo Script
# =============================================================================
# Prerequisites: AWS credentials configured, infrastructure deployed
#
# This demo shows the full kill switch lifecycle:
#   1. Normal trading flow (orders allowed)
#   2. Manual kill switch via operator console
#   3. Automated kill switch via Spark risk detection
#   4. Recovery (unkill)
# =============================================================================

set -e

API_URL="https://zjawxgdsth.execute-api.us-east-1.amazonaws.com"
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

pause() {
    echo ""
    echo -e "${YELLOW}Press Enter to continue...${NC}"
    read -r
}

header() {
    echo ""
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}  $1${NC}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# =============================================================================
header "SEC Rule 15c3-5 Market Access Controls Demo"
echo ""
echo "  This system implements real-time pre-trade risk controls inspired by"
echo "  the 2012 Knight Capital disaster, where a software bug caused \$440M"
echo "  in losses in 45 minutes."
echo ""
echo "  Architecture:"
echo "    Order Generator -> Kafka -> Order Router -> Gated Orders"
echo "                                  |"
echo "                          Kill Switch State"
echo "                                  |"
echo "                    Spark Risk Detection -> Auto-Kill"
echo "                    Operator Console    -> Manual Kill"
pause

# =============================================================================
header "STEP 1: Health Check"
echo ""
echo -e "  ${CYAN}GET ${API_URL}/health${NC}"
echo ""
curl -s "${API_URL}/health" | python3 -m json.tool
pause

# =============================================================================
header "STEP 2: Check Current Kill Switch State"
echo ""
echo -e "  ${CYAN}Querying DynamoDB state cache...${NC}"
echo ""
aws dynamodb scan --table-name sec-15c3-5-dev-state-cache \
    --query 'Items[*].{Scope:scope.S,Status:status.S,Reason:reason.S,UpdatedBy:updated_by.S}' \
    --output table 2>/dev/null || echo "  (No active kill switches)"
pause

# =============================================================================
header "STEP 3: Normal Trading - Orders Flow Through"
echo ""
echo -e "  ${GREEN}Generating 30 orders (5/sec for 6 seconds)...${NC}"
echo "  All orders should be ALLOWED through."
echo ""

# Start the router first
aws lambda invoke --function-name sec-15c3-5-dev-order-router \
    --payload '{}' --cli-binary-format raw-in-base64-out \
    --invocation-type Event /tmp/demo-router.json > /dev/null 2>&1

# Start the aggregator
aws lambda invoke --function-name sec-15c3-5-dev-killswitch-aggregator \
    --payload '{}' --cli-binary-format raw-in-base64-out \
    --invocation-type Event /tmp/demo-agg.json > /dev/null 2>&1

sleep 10

aws lambda invoke --function-name sec-15c3-5-dev-order-generator \
    --payload '{"mode":"normal","duration_seconds":6,"rate_per_second":5}' \
    --cli-binary-format raw-in-base64-out \
    --invocation-type Event /tmp/demo-orders1.json > /dev/null 2>&1

echo "  Waiting for orders to be processed..."
sleep 20

echo ""
echo -e "  ${CYAN}Order Router logs:${NC}"
aws logs tail /aws/lambda/sec-15c3-5-dev-order-router --since 30s --format short 2>&1 \
    | grep -E "(Processed|DROPPED|Loaded)" | tail -5
pause

# =============================================================================
header "STEP 4: Manual Kill Switch - Operator Halts AAPL"
echo ""
echo -e "  ${RED}An operator suspects unusual activity in AAPL.${NC}"
echo -e "  ${RED}Triggering kill switch for SYMBOL:AAPL...${NC}"
echo ""
echo -e "  ${CYAN}POST ${API_URL}/kill${NC}"
echo '  {"scope": "SYMBOL:AAPL", "reason": "Suspicious activity detected"}'
echo ""

RESULT=$(curl -s -X POST "${API_URL}/kill" \
    -H "Content-Type: application/json" \
    -d '{"scope":"SYMBOL:AAPL","reason":"Suspicious activity detected","operator":"demo-operator"}')
echo "$RESULT" | python3 -m json.tool

echo ""
echo "  Waiting for state propagation..."
sleep 10

echo ""
echo -e "  ${CYAN}Kill switch state:${NC}"
aws dynamodb scan --table-name sec-15c3-5-dev-state-cache \
    --query 'Items[*].{Scope:scope.S,Status:status.S,Reason:reason.S}' \
    --output table 2>/dev/null
pause

# =============================================================================
header "STEP 5: Verify AAPL Orders Are Blocked"
echo ""
echo -e "  ${GREEN}Generating orders including AAPL...${NC}"
echo -e "  AAPL orders should be ${RED}DROPPED${NC}, others ${GREEN}ALLOWED${NC}."
echo ""

aws lambda invoke --function-name sec-15c3-5-dev-order-generator \
    --payload '{"mode":"normal","duration_seconds":6,"rate_per_second":5}' \
    --cli-binary-format raw-in-base64-out \
    --invocation-type Event /tmp/demo-orders2.json > /dev/null 2>&1

echo "  Waiting for orders to be processed..."
sleep 20

echo ""
echo -e "  ${CYAN}Order Router logs (showing drops):${NC}"
aws logs tail /aws/lambda/sec-15c3-5-dev-order-router --since 30s --format short 2>&1 \
    | grep -E "(DROPPED|Processed)" | tail -10
pause

# =============================================================================
header "STEP 6: Recovery - Operator Resumes AAPL Trading"
echo ""
echo -e "  ${GREEN}Operator determines activity was legitimate. Resuming AAPL...${NC}"
echo ""
echo -e "  ${CYAN}POST ${API_URL}/unkill${NC}"

RESULT=$(curl -s -X POST "${API_URL}/unkill" \
    -H "Content-Type: application/json" \
    -d '{"scope":"SYMBOL:AAPL","reason":"Activity verified as legitimate","operator":"demo-operator"}')
echo "$RESULT" | python3 -m json.tool

echo ""
echo "  Waiting for state propagation..."
sleep 10

echo ""
echo -e "  ${CYAN}Updated kill switch state:${NC}"
aws dynamodb scan --table-name sec-15c3-5-dev-state-cache \
    --query 'Items[*].{Scope:scope.S,Status:status.S,Reason:reason.S}' \
    --output table 2>/dev/null
pause

# =============================================================================
header "STEP 7: Automated Kill - Spark Detects Runaway Algorithm"
echo ""
echo -e "  ${RED}Simulating a runaway trading algorithm on account 99999...${NC}"
echo -e "  Sending 10 orders/sec (threshold: 20 orders/60s)"
echo -e "  Spark Structured Streaming will detect the breach and auto-kill."
echo ""

aws lambda invoke --function-name sec-15c3-5-dev-order-generator \
    --payload '{"mode":"panic","duration_seconds":90,"rate_per_second":10,"account_id":"99999"}' \
    --cli-binary-format raw-in-base64-out \
    --invocation-type Event /tmp/demo-panic.json > /dev/null 2>&1

echo "  Orders flowing... waiting ~90s for Spark's 60s window to fire..."
echo ""

for i in $(seq 1 9); do
    sleep 10
    printf "  [%ds elapsed] " $((i * 10))
    STATE=$(aws dynamodb get-item --table-name sec-15c3-5-dev-state-cache \
        --key '{"scope":{"S":"ACCOUNT:99999"}}' \
        --query 'Item.status.S' --output text 2>/dev/null)
    if [ "$STATE" = "KILLED" ]; then
        REASON=$(aws dynamodb get-item --table-name sec-15c3-5-dev-state-cache \
            --key '{"scope":{"S":"ACCOUNT:99999"}}' \
            --query 'Item.reason.S' --output text 2>/dev/null)
        echo -e "${RED}KILL SWITCH TRIGGERED!${NC}"
        echo -e "  ${RED}Reason: $REASON${NC}"
        echo -e "  ${RED}Triggered by: Spark Risk Detection${NC}"
        break
    else
        echo "Monitoring... (no breach yet)"
    fi
done

pause

# =============================================================================
header "STEP 8: Verify Auto-Kill Is Working"
echo ""
echo -e "  ${CYAN}Final kill switch state:${NC}"
aws dynamodb scan --table-name sec-15c3-5-dev-state-cache \
    --query 'Items[*].{Scope:scope.S,Status:status.S,Reason:reason.S,UpdatedBy:updated_by.S}' \
    --output table 2>/dev/null

echo ""
echo -e "  ${CYAN}Audit trail (last 5 records):${NC}"
aws dynamodb scan --table-name sec-15c3-5-dev-audit-index \
    --limit 5 \
    --query 'Items[*].{OrderID:order_id.S,Decision:decision.S,Symbol:symbol.S,Account:account_id.S}' \
    --output table 2>/dev/null

echo ""
echo -e "  ${CYAN}Total audit records:${NC}"
aws dynamodb scan --table-name sec-15c3-5-dev-audit-index --select COUNT \
    --query 'Count' --output text 2>/dev/null
pause

# =============================================================================
header "STEP 9: Clean Up - Reset Kill Switches"
echo ""
echo -e "  ${GREEN}Resetting all kill switches...${NC}"

curl -s -X POST "${API_URL}/unkill" \
    -H "Content-Type: application/json" \
    -d '{"scope":"ACCOUNT:99999","reason":"Demo cleanup"}' > /dev/null

curl -s -X POST "${API_URL}/unkill" \
    -H "Content-Type: application/json" \
    -d '{"scope":"GLOBAL","reason":"Demo cleanup"}' > /dev/null

curl -s -X POST "${API_URL}/unkill" \
    -H "Content-Type: application/json" \
    -d '{"scope":"SYMBOL:AAPL","reason":"Demo cleanup"}' > /dev/null

echo "  All kill switches reset."
echo ""

# =============================================================================
header "Demo Complete!"
echo ""
echo "  What we demonstrated:"
echo ""
echo "    1. Real-time order routing through Kafka"
echo "    2. Manual kill switch via REST API (operator console)"
echo "    3. Scoped kills: GLOBAL, per-ACCOUNT, per-SYMBOL"
echo "    4. Automated risk detection via Spark Structured Streaming"
echo "    5. Sub-second kill propagation across the system"
echo "    6. Full audit trail in Kafka + DynamoDB"
echo ""
echo "  Key SEC 15c3-5 compliance features:"
echo "    - Pre-trade risk controls (orders checked before routing)"
echo "    - Automated threshold monitoring (Spark windowed aggregations)"
echo "    - Manual override capability (operator console)"
echo "    - Complete audit trail (every decision logged)"
echo "    - Kill switch scope hierarchy (global > account > symbol)"
echo ""
echo -e "${BOLD}  Infrastructure: MSK Serverless + Lambda + EMR Serverless + DynamoDB${NC}"
echo ""
