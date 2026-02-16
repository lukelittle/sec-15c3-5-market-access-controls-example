#!/bin/bash
set -e

TOPIC=$1

if [ -z "$TOPIC" ]; then
  echo "Usage: $0 <topic-name>"
  echo ""
  echo "Available topics:"
  echo "  orders.v1"
  echo "  risk_signals.v1"
  echo "  killswitch.commands.v1"
  echo "  killswitch.state.v1"
  echo "  orders.gated.v1"
  echo "  audit.v1"
  exit 1
fi

# Get MSK bootstrap brokers
if [ -z "$MSK_BOOTSTRAP" ]; then
  cd terraform/envs/dev
  export MSK_BOOTSTRAP=$(terraform output -raw msk_bootstrap_brokers)
  cd ../../..
fi

echo "Tailing topic: $TOPIC"
echo "Bootstrap: $MSK_BOOTSTRAP"
echo "Press Ctrl+C to stop"
echo ""

# Use kcat (kafkacat) if available, otherwise kafka-console-consumer
if command -v kcat &> /dev/null; then
  kcat -C -b $MSK_BOOTSTRAP -t $TOPIC -f 'Key: %k\nValue: %s\n---\n'
else
  kafka-console-consumer --bootstrap-server $MSK_BOOTSTRAP \
    --topic $TOPIC \
    --from-beginning \
    --property print.key=true \
    --property print.timestamp=true
fi
