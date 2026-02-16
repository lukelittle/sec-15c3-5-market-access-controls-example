"""
Order Router Lambda
Consumes orders from orders.v1
Checks kill switch state from killswitch.state.v1 (compacted)
Routes allowed orders to orders.gated.v1
Writes audit trail to audit.v1 and DynamoDB
"""
import json
import os
import time
import uuid
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
import boto3
from collections import defaultdict

# Configuration
BOOTSTRAP_SERVERS = os.environ['MSK_BOOTSTRAP_BROKERS']
ORDERS_TOPIC = 'orders.v1'
STATE_TOPIC = 'killswitch.state.v1'
GATED_TOPIC = 'orders.gated.v1'
AUDIT_TOPIC = 'audit.v1'
DYNAMODB_AUDIT_TABLE = os.environ['DYNAMODB_AUDIT_TABLE']
CONSUMER_GROUP = 'order-router'

dynamodb = boto3.resource('dynamodb')
audit_table = dynamodb.Table(DYNAMODB_AUDIT_TABLE)

# In-memory kill state cache
kill_state = {}

def create_consumer(topics):
    """Create Kafka consumer with IAM auth"""
    return KafkaConsumer(
        *topics,
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

def load_kill_state(consumer):
    """
    Bootstrap kill state from compacted topic
    Read all messages to get latest state per scope
    """
    print("Loading kill state from compacted topic...")
    
    # Temporarily subscribe to state topic only
    consumer.subscribe([STATE_TOPIC])
    
    # Poll until we've read all available messages
    state_count = 0
    empty_polls = 0
    max_empty_polls = 3
    
    while empty_polls < max_empty_polls:
        records = consumer.poll(timeout_ms=1000, max_records=100)
        
        if not records:
            empty_polls += 1
            continue
        
        empty_polls = 0
        
        for topic_partition, messages in records.items():
            for message in messages:
                state = message.value
                scope = state['scope']
                kill_state[scope] = state
                state_count += 1
    
    print(f"Loaded {state_count} state records, {len(kill_state)} unique scopes")
    
    # Now subscribe to both topics
    consumer.subscribe([ORDERS_TOPIC, STATE_TOPIC])

def check_kill_status(order):
    """
    Check if order should be killed based on scope hierarchy
    Returns (should_kill, matched_scopes, reason)
    """
    account_id = order['account_id']
    symbol = order['symbol']
    
    # Check scopes in order of specificity
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
    """
    Route order through kill switch logic
    Returns audit event
    """
    should_kill, matched_scopes, reason = check_kill_status(order)
    
    corr_id = str(uuid.uuid4())
    
    if should_kill:
        decision = 'DROP'
        print(f"DROPPED order {order['order_id']}: {reason}")
    else:
        decision = 'ALLOW'
        # Forward to gated topic
        try:
            producer.send(
                GATED_TOPIC,
                key=order['account_id'],
                value=order
            )
        except KafkaError as e:
            print(f"Error forwarding order: {e}")
            raise
    
    # Create audit event
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
    
    # Publish audit event
    try:
        producer.send(
            AUDIT_TOPIC,
            key=order['order_id'],
            value=audit_event
        )
    except KafkaError as e:
        print(f"Error publishing audit event: {e}")
    
    # Write to DynamoDB audit index (async, best effort)
    try:
        audit_table.put_item(Item={
            'order_id': order['order_id'],
            'ts': audit_event['ts'],
            'account_id': order['account_id'],
            'symbol': order['symbol'],
            'decision': decision,
            'reason': audit_event['reason'],
            'corr_id': corr_id,
            'ttl': int(time.time()) + (86400 * 30)  # 30 day TTL
        })
    except Exception as e:
        print(f"Error writing to DynamoDB audit: {e}")
        # Non-fatal; Kafka is source of truth
    
    return audit_event

def lambda_handler(event, context):
    """
    Lambda handler for order routing
    Runs continuously processing orders
    """
    print("Starting order router...")
    
    consumer = create_consumer([ORDERS_TOPIC, STATE_TOPIC])
    producer = create_producer()
    
    # Bootstrap kill state
    load_kill_state(consumer)
    
    orders_processed = 0
    orders_allowed = 0
    orders_dropped = 0
    errors = 0
    
    try:
        remaining_ms = context.get_remaining_time_in_millis()
        timeout_buffer_ms = 10000
        deadline = time.time() + (remaining_ms - timeout_buffer_ms) / 1000
        
        for message in consumer:
            if time.time() >= deadline:
                print("Approaching Lambda timeout, stopping...")
                break
            
            try:
                # Update kill state if message is from state topic
                if message.topic == STATE_TOPIC:
                    state = message.value
                    scope = state['scope']
                    kill_state[scope] = state
                    print(f"Updated kill state: {scope} -> {state['status']}")
                    continue
                
                # Process order
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
                errors += 1
        
        producer.flush()
        
    finally:
        consumer.close()
        producer.close()
    
    result = {
        'orders_processed': orders_processed,
        'orders_allowed': orders_allowed,
        'orders_dropped': orders_dropped,
        'errors': errors,
        'kill_state_scopes': len(kill_state)
    }
    
    print(f"Router run complete: {json.dumps(result)}")
    
    return {
        'statusCode': 200,
        'body': json.dumps(result)
    }
