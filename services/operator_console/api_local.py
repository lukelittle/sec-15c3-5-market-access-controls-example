"""
Local operator console - Flask HTTP server without AWS dependencies.
Publishes kill/unkill commands to Kafka.
Reads state and audit from Kafka topics for dashboard compatibility.
"""
import json
import os
import time
import uuid
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError

BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
COMMANDS_TOPIC = 'killswitch.commands.v1'
STATE_TOPIC = 'killswitch.state.v1'
AUDIT_TOPIC = 'audit.v1'

app = Flask(__name__)
CORS(app)  # Enable CORS for dashboard

# In-memory cache for state and audit (updated by background consumers)
kill_switch_state = {}
audit_records = []
AUDIT_MAX = 200
state_lock = threading.Lock()
audit_lock = threading.Lock()


def get_producer():
    return KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS.split(','),
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda k: k.encode('utf-8') if k else None,
        acks='all',
        retries=3
    )


def publish_command(action, scope, reason, operator='api'):
    cmd_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    command = {
        'cmd_id': cmd_id,
        'ts': int(time.time() * 1000),
        'scope': scope,
        'action': action,
        'reason': reason,
        'triggered_by': operator,
        'corr_id': corr_id
    }

    producer = get_producer()
    try:
        future = producer.send(COMMANDS_TOPIC, key=scope, value=command)
        future.get(timeout=10)
        print(f"Published command: {cmd_id} - {scope} {action}")
        return {'success': True, 'cmd_id': cmd_id, 'corr_id': corr_id, 'command': command}
    except KafkaError as e:
        print(f"Error publishing command: {e}")
        return {'success': False, 'error': str(e)}
    finally:
        producer.close()


def validate_scope(scope):
    if not scope:
        return False, 'Missing required field: scope'
    if not (scope == 'GLOBAL' or scope.startswith('ACCOUNT:') or scope.startswith('SYMBOL:')):
        return False, 'Invalid scope format. Use GLOBAL, ACCOUNT:<id>, or SYMBOL:<symbol>'
    return True, None


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': 'operator-console'})


@app.route('/kill', methods=['POST'])
def kill():
    body = request.get_json(force=True, silent=True) or {}
    scope = body.get('scope')
    reason = body.get('reason', 'Manual operator action')
    operator = body.get('operator', 'api')

    valid, error = validate_scope(scope)
    if not valid:
        return jsonify({'error': error}), 400

    result = publish_command('KILL', scope, reason, operator)
    if result['success']:
        return jsonify(result)
    return jsonify(result), 500


@app.route('/unkill', methods=['POST'])
def unkill():
    body = request.get_json(force=True, silent=True) or {}
    scope = body.get('scope')
    reason = body.get('reason', 'Manual operator action')
    operator = body.get('operator', 'api')

    valid, error = validate_scope(scope)
    if not valid:
        return jsonify({'error': error}), 400

    result = publish_command('UNKILL', scope, reason, operator)
    if result['success']:
        return jsonify(result)
    return jsonify(result), 500


@app.route('/state', methods=['GET'])
def get_state():
    """Return current kill switch state."""
    with state_lock:
        items = list(kill_switch_state.values())
    return jsonify(items)


@app.route('/audit', methods=['GET'])
def get_audit():
    """Return recent audit records."""
    with audit_lock:
        items = list(audit_records)
    return jsonify(items)


def consume_state():
    """Background thread to consume kill switch state from Kafka."""
    print("Starting state consumer...")
    time.sleep(5)  # Wait for Kafka to be ready
    try:
        consumer = KafkaConsumer(
            STATE_TOPIC,
            bootstrap_servers=BOOTSTRAP_SERVERS.split(','),
            value_deserializer=lambda v: json.loads(v.decode('utf-8')) if v else None,
            key_deserializer=lambda k: k.decode('utf-8') if k else None,
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            group_id='operator-console-state',
            consumer_timeout_ms=1000
        )
        print(f"State consumer connected, reading from {STATE_TOPIC}")
        while True:
            try:
                for msg in consumer:
                    if msg.value:
                        with state_lock:
                            kill_switch_state[msg.key] = msg.value
                        print(f"State update: {msg.key} -> {msg.value.get('status')}")
            except Exception as e:
                print(f"State consumer error: {e}")
            time.sleep(0.5)
    except Exception as e:
        print(f"State consumer failed to start: {e}")


def consume_audit():
    """Background thread to consume audit records from Kafka."""
    print("Starting audit consumer...")
    time.sleep(5)  # Wait for Kafka to be ready
    try:
        consumer = KafkaConsumer(
            AUDIT_TOPIC,
            bootstrap_servers=BOOTSTRAP_SERVERS.split(','),
            value_deserializer=lambda v: json.loads(v.decode('utf-8')) if v else None,
            auto_offset_reset='latest',
            enable_auto_commit=True,
            group_id='operator-console-audit',
            consumer_timeout_ms=1000
        )
        print(f"Audit consumer connected, reading from {AUDIT_TOPIC}")
        while True:
            try:
                for msg in consumer:
                    if msg.value:
                        with audit_lock:
                            audit_records.insert(0, msg.value)
                            if len(audit_records) > AUDIT_MAX:
                                audit_records.pop()
                        print(f"Audit record: {msg.value.get('order_id', 'unknown')[:8]} - {msg.value.get('decision')}")
            except Exception as e:
                print(f"Audit consumer error: {e}")
            time.sleep(0.5)
    except Exception as e:
        print(f"Audit consumer failed to start: {e}")


if __name__ == '__main__':
    print("Starting operator console (local) on port 8000...")

    # Start background consumers
    state_thread = threading.Thread(target=consume_state, daemon=True)
    audit_thread = threading.Thread(target=consume_audit, daemon=True)
    state_thread.start()
    audit_thread.start()

    app.run(host='0.0.0.0', port=8000)
