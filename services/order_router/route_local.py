"""
Local order router - standalone version without AWS dependencies.
Bootstraps kill state from compacted topic, routes orders, publishes audit.
Uses in-memory state instead of DynamoDB.
"""
import json
import os
import time
import uuid
import signal
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
ORDERS_TOPIC = 'orders.v1'
STATE_TOPIC = 'killswitch.state.v1'
GATED_TOPIC = 'orders.gated.v1'
AUDIT_TOPIC = 'audit.v1'
CONSUMER_GROUP = 'order-router'

# In-memory kill state cache
kill_state = {}

running = True

def handle_signal(sig, frame):
    global running
    print("Shutting down...")
    running = False

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def create_consumer(topics):
    return KafkaConsumer(
        *topics,
        bootstrap_servers=BOOTSTRAP_SERVERS.split(','),
        group_id=CONSUMER_GROUP,
        value_deserializer=lambda v: json.loads(v.decode('utf-8')),
        key_deserializer=lambda k: k.decode('utf-8') if k else None,
        auto_offset_reset='earliest',
        enable_auto_commit=True
    )


def create_producer():
    return KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS.split(','),
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda k: k.encode('utf-8') if k else None,
        acks='all',
        retries=3
    )


def load_kill_state():
    """Bootstrap kill state from compacted topic."""
    print("Loading kill state from compacted topic...")
    consumer = KafkaConsumer(
        STATE_TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS.split(','),
        group_id=f'{CONSUMER_GROUP}-bootstrap-{uuid.uuid4().hex[:8]}',
        value_deserializer=lambda v: json.loads(v.decode('utf-8')),
        key_deserializer=lambda k: k.decode('utf-8') if k else None,
        auto_offset_reset='earliest',
        enable_auto_commit=False,
        consumer_timeout_ms=5000
    )

    state_count = 0
    empty_polls = 0

    while empty_polls < 3:
        records = consumer.poll(timeout_ms=1000, max_records=100)
        if not records:
            empty_polls += 1
            continue
        empty_polls = 0
        for tp, messages in records.items():
            for message in messages:
                state = message.value
                kill_state[state['scope']] = state
                state_count += 1

    consumer.close()
    print(f"Loaded {state_count} state records, {len(kill_state)} unique scopes")
    for scope, state in kill_state.items():
        print(f"  {scope} -> {state['status']}")


def check_kill_status(order):
    account_id = order['account_id']
    symbol = order['symbol']

    scopes_to_check = [
        'GLOBAL',
        f'ACCOUNT:{account_id}',
        f'SYMBOL:{symbol}'
    ]

    matched_scopes = []
    for scope in scopes_to_check:
        if scope in kill_state:
            state = kill_state[scope]
            matched_scopes.append(scope)
            if state['status'] == 'KILLED':
                return True, matched_scopes, state.get('reason', 'Kill switch active')

    return False, matched_scopes, None


def route_order(order, producer):
    should_kill, matched_scopes, reason = check_kill_status(order)
    corr_id = str(uuid.uuid4())

    if should_kill:
        decision = 'DROP'
        print(f"DROPPED order {order['order_id'][:8]}... account={order['account_id']} symbol={order['symbol']}: {reason}")
    else:
        decision = 'ALLOW'
        try:
            producer.send(GATED_TOPIC, key=order['account_id'], value=order)
        except KafkaError as e:
            print(f"Error forwarding order: {e}")
            raise

    audit_event = {
        'ts': int(time.time() * 1000),
        'decision': decision,
        'order_id': order['order_id'],
        'account_id': order['account_id'],
        'symbol': order['symbol'],
        'scope_matches': matched_scopes,
        'killswitch_status': 'KILLED' if should_kill else 'ACTIVE',
        'reason': reason or 'No kill switch active',
        'corr_id': corr_id,
        'service': 'order_router'
    }

    try:
        producer.send(AUDIT_TOPIC, key=order['order_id'], value=audit_event)
    except KafkaError as e:
        print(f"Error publishing audit event: {e}")

    return audit_event


def main():
    print("Starting order router (local)...")

    # Bootstrap kill state first
    load_kill_state()

    # Now consume both orders and state updates
    consumer = create_consumer([ORDERS_TOPIC, STATE_TOPIC])
    producer = create_producer()

    orders_processed = 0
    orders_allowed = 0
    orders_dropped = 0

    try:
        while running:
            records = consumer.poll(timeout_ms=1000, max_records=100)
            for tp, messages in records.items():
                for message in messages:
                    try:
                        if message.topic == STATE_TOPIC:
                            state = message.value
                            scope = state['scope']
                            kill_state[scope] = state
                            print(f"Kill state update: {scope} -> {state['status']}")
                            continue

                        order = message.value
                        audit_event = route_order(order, producer)

                        orders_processed += 1
                        if audit_event['decision'] == 'ALLOW':
                            orders_allowed += 1
                        else:
                            orders_dropped += 1

                        if orders_processed % 100 == 0:
                            print(f"Processed {orders_processed} orders (allowed: {orders_allowed}, dropped: {orders_dropped})")

                    except Exception as e:
                        print(f"Error processing message: {e}")

            producer.flush()

    finally:
        consumer.close()
        producer.close()

    print(f"Router stopped: processed={orders_processed}, allowed={orders_allowed}, dropped={orders_dropped}")


if __name__ == '__main__':
    main()
