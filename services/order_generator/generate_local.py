"""
Local order generator - standalone version without AWS dependencies.
Produces synthetic orders to Kafka orders.v1 topic.
Supports MODE=normal (default) or MODE=panic via environment variable.
"""
import json
import os
import time
import uuid
import random
import signal
import sys
from kafka import KafkaProducer
from kafka.errors import KafkaError

BOOTSTRAP_SERVERS = os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
TOPIC = 'orders.v1'

SYMBOLS = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'NVDA', 'META', 'NFLX']
STRATEGIES = ['ALGO_X', 'ALGO_Y', 'MANUAL', 'SMART_ROUTER']
SIDES = ['BUY', 'SELL']

running = True

def handle_signal(sig, frame):
    global running
    print("Shutting down...")
    running = False

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def create_producer():
    return KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS.split(','),
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda k: k.encode('utf-8') if k else None,
        acks='all',
        retries=3
    )


def generate_order(account_id=None, symbol=None, panic_mode=False):
    if panic_mode:
        account_id = account_id or f"{random.randint(10000, 99999)}"
        symbol = symbol or random.choice(SYMBOLS[:3])
        qty = random.randint(500, 2000)
        price = round(random.uniform(100, 300), 2)
    else:
        account_id = account_id or f"{random.randint(10000, 99999)}"
        symbol = symbol or random.choice(SYMBOLS)
        qty = random.randint(10, 500)
        price = round(random.uniform(50, 500), 2)

    return {
        'order_id': str(uuid.uuid4()),
        'ts': int(time.time() * 1000),
        'account_id': account_id,
        'symbol': symbol,
        'side': random.choice(SIDES),
        'qty': qty,
        'price': price,
        'strategy': random.choice(STRATEGIES)
    }


def main():
    mode = os.environ.get('MODE', 'normal')
    duration = int(os.environ.get('DURATION_SECONDS', '0'))  # 0 = run forever
    account_id = os.environ.get('ACCOUNT_ID')
    symbol = os.environ.get('SYMBOL')
    panic_mode = mode == 'panic'

    if panic_mode:
        rate = int(os.environ.get('RATE_PER_SECOND', '50'))
    else:
        rate = int(os.environ.get('RATE_PER_SECOND', '5'))

    print(f"Starting order generation: mode={mode}, rate={rate}/s, duration={'forever' if duration == 0 else f'{duration}s'}")

    producer = create_producer()
    orders_sent = 0
    errors = 0
    start_time = time.time()

    try:
        while running:
            if duration > 0 and (time.time() - start_time) >= duration:
                break

            batch_start = time.time()

            for _ in range(rate):
                if not running:
                    break
                try:
                    order = generate_order(
                        account_id=account_id,
                        symbol=symbol,
                        panic_mode=panic_mode
                    )
                    producer.send(TOPIC, key=order['account_id'], value=order)
                    orders_sent += 1

                    if orders_sent % 100 == 0:
                        print(f"Sent {orders_sent} orders...")

                except KafkaError as e:
                    print(f"Kafka error: {e}")
                    errors += 1

            producer.flush()

            elapsed = time.time() - batch_start
            sleep_time = max(0, 1.0 - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)

    finally:
        producer.flush()
        producer.close()

    print(f"Order generation complete: sent={orders_sent}, errors={errors}")


if __name__ == '__main__':
    main()
