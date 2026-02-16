#!/bin/bash
set -e

# Get MSK bootstrap brokers from Terraform output
if [ -z "$MSK_BOOTSTRAP" ]; then
  echo "Getting MSK bootstrap brokers from Terraform..."
  cd terraform/envs/dev
  export MSK_BOOTSTRAP=$(terraform output -raw msk_bootstrap_brokers)
  cd ../../..
fi

echo "MSK Bootstrap Brokers: $MSK_BOOTSTRAP"

# Topic configurations
TOPICS=(
  "orders.v1:3:1"
  "risk_signals.v1:3:1"
  "killswitch.commands.v1:3:1"
  "killswitch.state.v1:3:1:compact"
  "orders.gated.v1:3:1"
  "audit.v1:3:1"
)

echo "Creating Kafka topics..."

for topic_config in "${TOPICS[@]}"; do
  IFS=':' read -r topic partitions replication cleanup <<< "$topic_config"
  
  echo "Creating topic: $topic (partitions=$partitions, replication=$replication)"
  
  if [ "$cleanup" == "compact" ]; then
    # Compacted topic for kill switch state
    kafka-topics --bootstrap-server $MSK_BOOTSTRAP \
      --command-config /tmp/client.properties \
      --create \
      --topic $topic \
      --partitions $partitions \
      --replication-factor $replication \
      --config cleanup.policy=compact \
      --config min.cleanable.dirty.ratio=0.01 \
      --config segment.ms=60000 \
      --if-not-exists
  else
    # Regular topic
    kafka-topics --bootstrap-server $MSK_BOOTSTRAP \
      --command-config /tmp/client.properties \
      --create \
      --topic $topic \
      --partitions $partitions \
      --replication-factor $replication \
      --if-not-exists
  fi
done

echo ""
echo "✓ Topics created successfully"
echo ""
echo "Verify topics:"
echo "  kafka-topics --bootstrap-server \$MSK_BOOTSTRAP --command-config /tmp/client.properties --list"
echo ""
echo "Describe compacted topic:"
echo "  kafka-topics --bootstrap-server \$MSK_BOOTSTRAP --command-config /tmp/client.properties --describe --topic killswitch.state.v1"
