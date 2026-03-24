"""
Operator Console Lambda
API endpoints for manual kill switch control
Publishes commands to killswitch.commands.v1
"""
import json
import os
import time
import uuid
from kafka import KafkaProducer
from kafka.errors import KafkaError
from kafka.oauth.abstract import AbstractTokenProvider
from aws_msk_iam_sasl_signer import MSKAuthTokenProvider

# Configuration
BOOTSTRAP_SERVERS = os.environ['MSK_BOOTSTRAP_BROKERS']
COMMANDS_TOPIC = 'killswitch.commands.v1'
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

class MSKTokenProvider(AbstractTokenProvider):
    def token(self):
        token, _ = MSKAuthTokenProvider.generate_auth_token(AWS_REGION)
        return token

def create_producer():
    """Create Kafka producer with IAM auth"""
    return KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS.split(','),
        security_protocol='SASL_SSL',
        sasl_mechanism='OAUTHBEARER',
        sasl_oauth_token_provider=MSKTokenProvider(),
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda k: k.encode('utf-8') if k else None,
        acks='all',
        retries=3,
        api_version=(2, 8, 0),
        request_timeout_ms=15000,
        max_block_ms=15000
    )

def publish_command(action, scope, reason, operator='api'):
    """
    Publish kill/unkill command to Kafka
    
    Args:
        action: "KILL" or "UNKILL"
        scope: "GLOBAL", "ACCOUNT:<id>", or "SYMBOL:<symbol>"
        reason: Human-readable reason
        operator: Who triggered this (default: "api")
    """
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
    
    producer = create_producer()
    
    try:
        future = producer.send(
            COMMANDS_TOPIC,
            key=scope,
            value=command
        )
        future.get(timeout=10)
        print(f"Published command: {cmd_id} - {scope} {action}")
        
        return {
            'success': True,
            'cmd_id': cmd_id,
            'corr_id': corr_id,
            'command': command
        }
    
    except KafkaError as e:
        print(f"Error publishing command: {e}")
        return {
            'success': False,
            'error': str(e)
        }
    
    finally:
        producer.close()

def lambda_handler(event, context):
    """
    Lambda handler for operator console API
    
    Routes:
        POST /kill - Trigger kill switch
        POST /unkill - Deactivate kill switch
        GET /health - Health check
    
    Body for /kill and /unkill:
    {
        "scope": "GLOBAL|ACCOUNT:<id>|SYMBOL:<symbol>",
        "reason": "Human-readable reason",
        "operator": "operator_name" (optional)
    }
    """
    print(f"Event: {json.dumps(event)}")
    
    # Parse request
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')
    path = event.get('requestContext', {}).get('http', {}).get('path', '/')
    
    # Health check
    if path == '/health' or path == '/':
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'status': 'healthy', 'service': 'operator-console'})
        }
    
    # Parse body
    try:
        body = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Invalid JSON body'})
        }
    
    scope = body.get('scope')
    reason = body.get('reason', 'Manual operator action')
    operator = body.get('operator', 'api')
    
    # Validate scope
    if not scope:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Missing required field: scope'})
        }
    
    # Validate scope format
    valid_scopes = ['GLOBAL']
    if not (scope == 'GLOBAL' or scope.startswith('ACCOUNT:') or scope.startswith('SYMBOL:')):
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Invalid scope format. Use GLOBAL, ACCOUNT:<id>, or SYMBOL:<symbol>'})
        }
    
    # Route to action
    if path == '/kill' and http_method == 'POST':
        result = publish_command('KILL', scope, reason, operator)
    elif path == '/unkill' and http_method == 'POST':
        result = publish_command('UNKILL', scope, reason, operator)
    else:
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Not found. Available endpoints: POST /kill, POST /unkill, GET /health'})
        }
    
    if result['success']:
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(result)
        }
    else:
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(result)
        }
