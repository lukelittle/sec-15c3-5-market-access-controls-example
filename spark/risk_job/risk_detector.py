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
    col, window, count, sum as spark_sum, avg, max as spark_max,
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

def create_spark_session():
    """Create Spark session with Kafka support"""
    return SparkSession.builder \
        .appName("RiskDetector") \
        .config("spark.sql.streaming.checkpointLocation", "/tmp/checkpoint") \
        .config("spark.sql.shuffle.partitions", "4") \
        .getOrCreate()

def read_orders_stream(spark):
    """Read orders from Kafka topic"""
    return spark \
        .readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("kafka.security.protocol", "SASL_SSL") \
        .option("kafka.sasl.mechanism", "AWS_MSK_IAM") \
        .option("kafka.sasl.jaas.config", 
                "software.amazon.msk.auth.iam.IAMLoginModule required;") \
        .option("kafka.sasl.client.callback.handler.class",
                "software.amazon.msk.auth.iam.IAMClientCallbackHandler") \
        .option("subscribe", "orders.v1") \
        .option("startingOffsets", "latest") \
        .load() \
        .select(
            from_json(col("value").cast("string"), order_schema).alias("order")
        ) \
        .select("order.*") \
        .withColumn("notional", col("qty") * col("price")) \
        .withColumn("event_time", (col("ts") / 1000).cast("timestamp"))

def compute_risk_signals(orders_df):
    """
    Compute risk signals using Spark SQL
    Uses 60-second tumbling windows per account
    """
    # Register as temp view for SQL
    orders_df.createOrReplaceTempView("orders")
    
    # Use Spark SQL for windowed aggregations
    risk_signals_sql = f"""
        SELECT
            window.start as window_start,
            window.end as window_end,
            account_id,
            COUNT(*) as order_count,
            SUM(notional) as total_notional,
            AVG(notional) as avg_notional,
            COUNT(DISTINCT symbol) as unique_symbols,
            MAX(symbol) as top_symbol,
            CAST(unix_timestamp(current_timestamp()) * 1000 AS BIGINT) as ts
        FROM orders
        GROUP BY
            window(event_time, '60 seconds'),
            account_id
    """
    
    spark = orders_df.sparkSession
    risk_signals = spark.sql(risk_signals_sql)
    
    # Add symbol concentration (requires additional aggregation)
    # For simplicity, we'll compute this in DataFrame API
    symbol_counts = orders_df \
        .groupBy(
            window(col("event_time"), "60 seconds"),
            col("account_id"),
            col("symbol")
        ) \
        .agg(count("*").alias("symbol_count"))
    
    symbol_counts.createOrReplaceTempView("symbol_counts")
    risk_signals.createOrReplaceTempView("risk_signals")
    
    # Join to get top symbol share
    enriched_signals_sql = """
        SELECT
            r.*,
            COALESCE(MAX(sc.symbol_count) / r.order_count, 0.0) as top_symbol_share
        FROM risk_signals r
        LEFT JOIN symbol_counts sc
            ON r.window_start = sc.window.start
            AND r.account_id = sc.account_id
        GROUP BY
            r.window_start, r.window_end, r.account_id,
            r.order_count, r.total_notional, r.avg_notional,
            r.unique_symbols, r.top_symbol, r.ts
    """
    
    return spark.sql(enriched_signals_sql)

def detect_threshold_breaches(risk_signals_df):
    """
    Detect threshold breaches and generate kill commands
    """
    # Add breach flags
    breaches = risk_signals_df \
        .withColumn("order_rate_breach", 
                   col("order_count") > lit(ORDER_RATE_THRESHOLD)) \
        .withColumn("notional_breach",
                   col("total_notional") > lit(NOTIONAL_THRESHOLD)) \
        .withColumn("concentration_breach",
                   col("top_symbol_share") > lit(SYMBOL_CONCENTRATION_THRESHOLD)) \
        .filter(
            col("order_rate_breach") | 
            col("notional_breach") | 
            col("concentration_breach")
        )
    
    # Generate kill commands
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
                   .when(col("concentration_breach"),
                        concat(lit("Symbol concentration breach: "),
                              (col("top_symbol_share") * 100).cast("string"),
                              lit("% in "), col("top_symbol")))
                   .otherwise(lit("Multiple breaches"))) \
        .withColumn("metric",
                   when(col("order_rate_breach"), lit("order_rate_60s"))
                   .when(col("notional_breach"), lit("notional_60s"))
                   .when(col("concentration_breach"), lit("symbol_concentration"))
                   .otherwise(lit("multiple"))) \
        .withColumn("value",
                   when(col("order_rate_breach"), col("order_count"))
                   .when(col("notional_breach"), col("total_notional"))
                   .when(col("concentration_breach"), col("top_symbol_share"))
                   .otherwise(lit(0.0)))
    
    return kill_commands.select(
        "cmd_id", "ts", "scope", "action", "reason",
        "triggered_by", "metric", "value", "corr_id"
    )

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
        .outputMode("append") \
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
