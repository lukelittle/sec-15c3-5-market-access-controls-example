"""
Kill Switch Aggregator Lambda
Consumes kill commands from killswitch.commands.v1
Produces authoritative state to killswitch.state.v1 (compacted topic)
Maintains state cache in DynamoDB for fast lookups
"""
import json
import os
import time
import uuid
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
import boto3

# Configuration
BOOTSTRAP_SERVERS = os.environ['MSK_BOOTSTRAP_BROKERS']
COMMANDS_TOPIC = 'killswitch.commands.v1'
STATE_TOPIC = 'killswitch.state.v1'
DYNAMODB_TABLE = os.environ['DYNAMODB_STATE_TABLE']
CONSUMER_GROUP = 'killswitch-aggregator'

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE)

def create_consumer():
    """Create Kafka consumer with IAM auth"""
    return KafkaConsumer(
        COMMANDS_TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS.split(','),
        security_protocol='SASL_SSL',
        sasl_mechanism='AWS_MSK_IAM',
        sasl_oauth_token_provider=lambda: get_aws_iam_token(),
        group_id=CONSUMER_GROUP,
        value_deserializer=lambda v: json.loads(v.decode('utf-8')),
        key_deserializer=lambda k: k.decode('utf-8') if k else None,
        auto_offset_reset='earliest',
        enable_auto_commit=True
    )

def create_producer():
    """Create Kafka producer with IAM auth"""
    return KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS.split(','),
        security_protocol='SASL_SSL',
        sasl_mechanism='AWS_MSK_IAM',
        sasl_oauth_token_provider=lambda: get_aws_iam_token(),
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda k: k.encode('utf-8') if k else None,
        acks='all',
        retries=3
    )

def get_aws_iam_token():
    """Get AWS IAM token for MSK authentication"""
    import boto3
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest
    
    session = boto3.Session()
    credentials = session.get_credentials()
    region = session.region_name or 'us-east-1'
    
    request = AWSRequest(
        method='GET',
        url=f'https://kafka.{region}.amazonaws.com/',
        headers={'host': f'kafka.{region}.amazonaws.com'}
    )
    
    SigV4Auth(credentials, 'kafka', region).add_auth(request)
    return request.headers['Authorization']

def process_command(command, producer):
    """
    Process a kill command and produce state update
    
    Command format:
    {
        "cmd_id": "uuid",
        "ts": 1710000000000,
        "scope": "GLOBAL|ACCOUNT:123|SYMBOL:AAPL",
        "action": "KILL|UNKILL",
        "reason": "...",
        "triggered_by": "spark|operator",
        "metric": "optional",
        "value": "optional",
        "corr_id": "uuid"
    }
    """
    scope = command['scope']
    action = command['action']
    
    # Determine new status
    if action == 'KILL':
        status = 'KILLED'
    elif action == 'UNKILL':
        status = 'ACTIVE'
    else:
        print(f"Unknown action: {action}")
        return
    
    # Create state record
    state = {
        'scope': scope,
        'status': status,
        'updated_ts': int(time.time() * 1000),
        'updated_by': command.get('triggered_by', 'unknown'),
        'reason': command.get('reason', ''),
        'last_cmd_id': command['cmd_id'],
        'corr_id': command.get('corr_id', str(uuid.uuid4()))
    }
    
    # Publish to compacted state topic (key = scope)
    try:
        future = producer.send(
            STATE_TOPIC,
            key=scope,
            value=state
        )
        future.get(timeout=10)
        print(f"Published state: {scope} -> {status}")
    except KafkaError as e:
        print(f"Error publishing state: {e}")
        raise
    
    # Update DynamoDB cache
    try:
        table.put_item(Item={
            'scope': scope,
            'status': status,
            'updated_ts': state['updated_ts'],
            'updated_by': state['updated_by'],
            'reason': state['reason'],
            'last_cmd_id': state['last_cmd_id'],
            'corr_id': state['corr_id'],
            'ttl': int(time.time()) + (86400 * 7)  # 7 day TTL
        })
        print(f"Updated DynamoDB cache: {scope}")
    except Exception as e:
        print(f"Error updating DynamoDB: {e}")
        # Non-fatal; Kafka is source of truth

def lambda_handler(event, context):
    """
    Lambda handler for kill switch aggregation
    Runs continuously processing commands
    """
    print("Starting kill switch aggregator...")
    
    consumer = create_consumer()
    producer = create_producer()
    
    commands_processed = 0
    errors = 0
    
    # Process messages until Lambda timeout
    try:
        # Get remaining time
        remaining_ms = context.get_remaining_time_in_millis()
        timeout_buffer_ms = 10000  # Stop 10s before timeout
        deadline = time.time() + (remaining_ms - timeout_buffer_ms) / 1000
        
        for message in consumer:
            if time.time() >= deadline:
                print("Approaching Lambda timeout, stopping...")
                break
            
            try:
                command = message.value
                print(f"Processing command: {command['cmd_id']} - {command['scope']} {command['action']}")
                
                process_command(command, producer)
                commands_processed += 1
                
            except Exception as e:
                print(f"Error processing command: {e}")
                errors += 1
        
        producer.flush()
        
    finally:
        consumer.close()
        producer.close()
    
    result = {
        'commands_processed': commands_processed,
        'errors': errors
    }
    
    print(f"Aggregator run complete: {json.dumps(result)}")
    
    return {
        'statusCode': 200,
        'body': json.dumps(result)
    }
