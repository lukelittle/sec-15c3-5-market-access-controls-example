"""
Order Generator Lambda
Generates synthetic order events and publishes to Kafka orders.v1 topic
Supports normal and panic modes for demo purposes
"""
import json
import os
import time
import uuid
import random
from datetime import datetime
from kafka import KafkaProducer
from kafka.errors import KafkaError

# Configuration
BOOTSTRAP_SERVERS = os.environ['MSK_BOOTSTRAP_BROKERS']
TOPIC = 'orders.v1'

# Synthetic data
SYMBOLS = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'NVDA', 'META', 'NFLX']
STRATEGIES = ['ALGO_X', 'ALGO_Y', 'MANUAL', 'SMART_ROUTER']
SIDES = ['BUY', 'SELL']

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
    
    # Create signing request
    request = AWSRequest(
        method='GET',
        url=f'https://kafka.{region}.amazonaws.com/',
        headers={'host': f'kafka.{region}.amazonaws.com'}
    )
    
    SigV4Auth(credentials, 'kafka', region).add_auth(request)
    return request.headers['Authorization']

def generate_order(account_id=None, symbol=None, panic_mode=False):
    """Generate a synthetic order event"""
    if panic_mode:
        # Panic mode: high volume, concentrated symbol
        account_id = account_id or f"{random.randint(10000, 99999)}"
        symbol = symbol or random.choice(SYMBOLS[:3])  # Concentrate on first 3
        qty = random.randint(500, 2000)  # Higher quantities
        price = round(random.uniform(100, 300), 2)
    else:
        # Normal mode: distributed
        account_id = account_id or f"{random.randint(10000, 99999)}"
        symbol = symbol or random.choice(SYMBOLS)
        qty = random.randint(10, 500)
        price = round(random.uniform(50, 500), 2)
    
    order = {
        'order_id': str(uuid.uuid4()),
        'ts': int(time.time() * 1000),
        'account_id': account_id,
        'symbol': symbol,
        'side': random.choice(SIDES),
        'qty': qty,
        'price': price,
        'strategy': random.choice(STRATEGIES)
    }
    
    return order

def lambda_handler(event, context):
    """
    Lambda handler for order generation
    
    Event payload:
    {
        "mode": "normal" | "panic",
        "duration_seconds": 300,
        "account_id": "12345",  # optional, for targeted panic
        "symbol": "AAPL",       # optional, for targeted panic
        "rate_per_second": 10   # optional, default varies by mode
    }
    """
    mode = event.get('mode', 'normal')
    duration = event.get('duration_seconds', 60)
    account_id = event.get('account_id')
    symbol = event.get('symbol')
    
    # Determine rate
    if mode == 'panic':
        rate = event.get('rate_per_second', 50)  # High rate for panic
    else:
        rate = event.get('rate_per_second', 5)   # Normal rate
    
    panic_mode = (mode == 'panic')
    
    print(f"Starting order generation: mode={mode}, duration={duration}s, rate={rate}/s")
    
    producer = create_producer()
    orders_sent = 0
    errors = 0
    
    start_time = time.time()
    end_time = start_time + duration
    
    try:
        while time.time() < end_time:
            batch_start = time.time()
            
            # Generate batch of orders
            for _ in range(rate):
                try:
                    order = generate_order(
                        account_id=account_id,
                        symbol=symbol,
                        panic_mode=panic_mode
                    )
                    
                    # Use account_id as key for partitioning
                    key = order['account_id']
                    
                    future = producer.send(TOPIC, key=key, value=order)
                    future.get(timeout=10)  # Wait for ack
                    
                    orders_sent += 1
                    
                    if orders_sent % 100 == 0:
                        print(f"Sent {orders_sent} orders...")
                
                except KafkaError as e:
                    print(f"Kafka error: {e}")
                    errors += 1
                except Exception as e:
                    print(f"Error generating order: {e}")
                    errors += 1
            
            # Sleep to maintain rate
            elapsed = time.time() - batch_start
            sleep_time = max(0, 1.0 - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        producer.flush()
        
    finally:
        producer.close()
    
    result = {
        'orders_sent': orders_sent,
        'errors': errors,
        'duration_seconds': int(time.time() - start_time),
        'mode': mode,
        'rate_per_second': rate
    }
    
    print(f"Order generation complete: {json.dumps(result)}")
    
    return {
        'statusCode': 200,
        'body': json.dumps(result)
    }
