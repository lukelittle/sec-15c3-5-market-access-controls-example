"""
Risk Detector Spark Streaming Job
Consumes orders from Kafka, computes risk signals using Spark SQL,
and emits kill commands when thresholds are breached.
"""
import sys
import json
import time
import uuid
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, window, count, sum as spark_sum, max as spark_max,
    from_json, to_json, struct, lit, current_timestamp, unix_timestamp,
    concat, when
)
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, IntegerType, DoubleType
)

# Configuration from environment/args
KAFKA_BOOTSTRAP_SERVERS = sys.argv[1] if len(sys.argv) > 1 else "localhost:9092"
ORDER_RATE_THRESHOLD = int(sys.argv[2]) if len(sys.argv) > 2 else 100
NOTIONAL_THRESHOLD = float(sys.argv[3]) if len(sys.argv) > 3 else 1000000
SYMBOL_CONCENTRATION_THRESHOLD = float(sys.argv[4]) if len(sys.argv) > 4 else 0.7

print(f"Starting Risk Detector with thresholds:")
print(f"  Order rate: {ORDER_RATE_THRESHOLD} orders/60s")
print(f"  Notional: ${NOTIONAL_THRESHOLD}/60s")
print(f"  Symbol concentration: {SYMBOL_CONCENTRATION_THRESHOLD}")

# Order schema
order_schema = StructType([
    StructField("order_id", StringType(), False),
    StructField("ts", LongType(), False),
    StructField("account_id", StringType(), False),
    StructField("symbol", StringType(), False),
    StructField("side", StringType(), False),
    StructField("qty", IntegerType(), False),
    StructField("price", DoubleType(), False),
    StructField("strategy", StringType(), False)
])

KAFKA_OPTIONS = {
    "kafka.bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
    "kafka.security.protocol": "SASL_SSL",
    "kafka.sasl.mechanism": "AWS_MSK_IAM",
    "kafka.sasl.jaas.config": "software.amazon.msk.auth.iam.IAMLoginModule required;",
    "kafka.sasl.client.callback.handler.class": "software.amazon.msk.auth.iam.IAMClientCallbackHandler",
}

def create_spark_session():
    """Create Spark session with Kafka support"""
    return SparkSession.builder \
        .appName("RiskDetector") \
        .config("spark.sql.streaming.checkpointLocation", "/tmp/checkpoint") \
        .config("spark.sql.shuffle.partitions", "4") \
        .config("spark.sql.streaming.statefulOperator.checkCorrectness.enabled", "false") \
        .getOrCreate()

def read_orders_stream(spark):
    """Read orders from Kafka topic"""
    reader = spark.readStream.format("kafka")
    for k, v in KAFKA_OPTIONS.items():
        reader = reader.option(k, v)

    return reader \
        .option("subscribe", "orders.v1") \
        .option("startingOffsets", "latest") \
        .load() \
        .select(
            from_json(col("value").cast("string"), order_schema).alias("order")
        ) \
        .select("order.*") \
        .withColumn("notional", col("qty") * col("price")) \
        .withColumn("event_time", (col("ts") / 1000).cast("timestamp")) \
        .withWatermark("event_time", "30 seconds")

def compute_risk_signals(orders_df):
    """
    Compute risk signals using a single-level windowed aggregation.
    Uses 60-second tumbling windows per account.
    """
    risk_signals = orders_df \
        .groupBy(
            window(col("event_time"), "60 seconds"),
            col("account_id")
        ) \
        .agg(
            count("*").alias("order_count"),
            spark_sum("notional").alias("total_notional"),
            spark_max("symbol").alias("top_symbol")
        ) \
        .withColumn("avg_notional", col("total_notional") / col("order_count")) \
        .withColumn("window_start", col("window.start")) \
        .withColumn("window_end", col("window.end")) \
        .withColumn("ts", (unix_timestamp(current_timestamp()) * 1000).cast("long")) \
        .drop("window")

    return risk_signals

def detect_threshold_breaches(risk_signals_df):
    """
    Detect threshold breaches and generate kill commands.
    Checks order rate and notional thresholds.
    """
    breaches = risk_signals_df \
        .withColumn("order_rate_breach",
                    col("order_count") > lit(ORDER_RATE_THRESHOLD)) \
        .withColumn("notional_breach",
                    col("total_notional") > lit(NOTIONAL_THRESHOLD)) \
        .filter(
            col("order_rate_breach") |
            col("notional_breach")
        )

    kill_commands = breaches \
        .withColumn("cmd_id", lit(str(uuid.uuid4()))) \
        .withColumn("scope",
                    concat(lit("ACCOUNT:"), col("account_id"))) \
        .withColumn("action", lit("KILL")) \
        .withColumn("triggered_by", lit("spark")) \
        .withColumn("corr_id", lit(str(uuid.uuid4()))) \
        .withColumn("reason",
                    when(col("order_rate_breach"),
                         concat(lit("Order rate breach: "),
                                col("order_count").cast("string"),
                                lit(" orders in 60s")))
                    .when(col("notional_breach"),
                         concat(lit("Notional breach: $"),
                                col("total_notional").cast("string"),
                                lit(" in 60s")))
                    .otherwise(lit("Multiple breaches"))) \
        .withColumn("metric",
                    when(col("order_rate_breach"), lit("order_rate_60s"))
                    .when(col("notional_breach"), lit("notional_60s"))
                    .otherwise(lit("multiple"))) \
        .withColumn("value",
                    when(col("order_rate_breach"), col("order_count"))
                    .when(col("notional_breach"), col("total_notional"))
                    .otherwise(lit(0.0)))

    return kill_commands.select(
        "cmd_id", "ts", "scope", "action", "reason",
        "triggered_by", "metric", "value", "corr_id"
    )

def write_to_kafka(df, topic, checkpoint_suffix, output_mode="update"):
    """Write a streaming DataFrame to a Kafka topic"""
    writer = df \
        .select(
            col(df.columns[0]).cast("string").alias("key") if "account_id" not in df.columns
            else col("account_id" if "account_id" in df.columns else "scope").alias("key"),
            to_json(struct("*")).alias("value")
        ) \
        .writeStream \
        .format("kafka") \
        .outputMode(output_mode)

    for k, v in KAFKA_OPTIONS.items():
        writer = writer.option(k, v)

    return writer \
        .option("topic", topic) \
        .option("checkpointLocation", f"/tmp/checkpoint/{checkpoint_suffix}") \
        .start()

def write_risk_signals(risk_signals_df):
    """Write risk signals to Kafka"""
    return risk_signals_df \
        .select(
            col("account_id").alias("key"),
            to_json(struct("*")).alias("value")
        ) \
        .writeStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("kafka.security.protocol", "SASL_SSL") \
        .option("kafka.sasl.mechanism", "AWS_MSK_IAM") \
        .option("kafka.sasl.jaas.config",
                "software.amazon.msk.auth.iam.IAMLoginModule required;") \
        .option("kafka.sasl.client.callback.handler.class",
                "software.amazon.msk.auth.iam.IAMClientCallbackHandler") \
        .option("topic", "risk_signals.v1") \
        .option("checkpointLocation", "/tmp/checkpoint/risk_signals") \
        .outputMode("update") \
        .start()

def write_kill_commands(kill_commands_df):
    """Write kill commands to Kafka"""
    return kill_commands_df \
        .select(
            col("scope").alias("key"),
            to_json(struct("*")).alias("value")
        ) \
        .writeStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("kafka.security.protocol", "SASL_SSL") \
        .option("kafka.sasl.mechanism", "AWS_MSK_IAM") \
        .option("kafka.sasl.jaas.config",
                "software.amazon.msk.auth.iam.IAMLoginModule required;") \
        .option("kafka.sasl.client.callback.handler.class",
                "software.amazon.msk.auth.iam.IAMClientCallbackHandler") \
        .option("topic", "killswitch.commands.v1") \
        .option("checkpointLocation", "/tmp/checkpoint/kill_commands") \
        .outputMode("update") \
        .start()

def main():
    """Main entry point"""
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    print("Reading orders stream...")
    orders_df = read_orders_stream(spark)

    print("Computing risk signals...")
    risk_signals_df = compute_risk_signals(orders_df)

    print("Detecting threshold breaches...")
    kill_commands_df = detect_threshold_breaches(risk_signals_df)

    print("Starting streaming queries...")

    # Write risk signals
    signals_query = write_risk_signals(risk_signals_df)

    # Write kill commands
    commands_query = write_kill_commands(kill_commands_df)

    # Console output for debugging
    console_query = risk_signals_df \
        .writeStream \
        .format("console") \
        .outputMode("update") \
        .option("truncate", False) \
        .start()

    print("Streaming queries started. Waiting for termination...")

    # Wait for termination
    spark.streams.awaitAnyTermination()

if __name__ == "__main__":
    main()
