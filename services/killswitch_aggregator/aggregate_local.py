"""
Local kill switch aggregator - standalone version without AWS dependencies.
Consumes kill commands, publishes authoritative state to compacted topic.
Uses in-memory dict instead of DynamoDB.
"""
import json
import os
import time
import uuid
import signal
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
COMMANDS_TOPIC = 'killswitch.commands.v1'
STATE_TOPIC = 'killswitch.state.v1'
CONSUMER_GROUP = 'killswitch-aggregator'

# In-memory state cache (replaces DynamoDB)
state_cache = {}

running = True

def handle_signal(sig, frame):
    global running
    print("Shutting down...")
    running = False

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def create_consumer():
    return KafkaConsumer(
        COMMANDS_TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS.split(','),
        group_id=CONSUMER_GROUP,
        value_deserializer=lambda v: json.loads(v.decode('utf-8')),
        key_deserializer=lambda k: k.decode('utf-8') if k else None,
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        consumer_timeout_ms=1000
    )


def create_producer():
    return KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS.split(','),
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda k: k.encode('utf-8') if k else None,
        acks='all',
        retries=3
    )


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

    # Publish to compacted state topic
    try:
        future = producer.send(STATE_TOPIC, key=scope, value=state)
        future.get(timeout=10)
        print(f"State update: {scope} -> {status} (reason: {state['reason']})")
    except KafkaError as e:
        print(f"Error publishing state: {e}")
        raise

    # Update in-memory cache (replaces DynamoDB)
    state_cache[scope] = state


def main():
    print("Starting kill switch aggregator (local)...")

    consumer = create_consumer()
    producer = create_producer()
    commands_processed = 0

    try:
        while running:
            records = consumer.poll(timeout_ms=1000, max_records=100)
            for tp, messages in records.items():
                for message in messages:
                    try:
                        command = message.value
                        print(f"Processing command: {command['cmd_id']} - {command['scope']} {command['action']}")
                        process_command(command, producer)
                        commands_processed += 1
                    except Exception as e:
                        print(f"Error processing command: {e}")

    finally:
        consumer.close()
        producer.close()

    print(f"Aggregator stopped: processed {commands_processed} commands")


if __name__ == '__main__':
    main()
