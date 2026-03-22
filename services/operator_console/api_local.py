"""
Local operator console - Flask HTTP server without AWS dependencies.
Publishes kill/unkill commands to Kafka.
"""
import json
import os
import time
import uuid
from flask import Flask, request, jsonify
from kafka import KafkaProducer
from kafka.errors import KafkaError

BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
COMMANDS_TOPIC = 'killswitch.commands.v1'

app = Flask(__name__)


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


if __name__ == '__main__':
    print("Starting operator console (local) on port 8000...")
    app.run(host='0.0.0.0', port=8000)
