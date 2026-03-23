# Section 5: Spark Windowing — Line-by-Line Code Walkthrough

**Duration:** 7 minutes
**Goal:** Walk through `spark/risk_job/risk_detector_local.py` line by line. This is the technical centerpiece of the talk.

**File:** `spark/risk_job/risk_detector_local.py` (219 lines)

---

## Opening

> "You learned about Spark Structured Streaming and windowing in weeks 9 and 10. Now let's look at what it looks like applied to a real problem. I'm going to walk through the actual code — every function, every line that matters."

Open the file in your editor or show it on screen. Walk through it top to bottom.

---

## Part 1: Configuration and Schema (Lines 1-41)

### Imports (Lines 1-18)

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, window, count, sum as spark_sum, avg, max as spark_max,
    from_json, to_json, struct, lit, current_timestamp, unix_timestamp,
    concat, when, approx_count_distinct, udf, collect_list
)
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, IntegerType, DoubleType, FloatType
)
```

> "Standard PySpark imports. Notice we import `sum as spark_sum` — that's because Python has a built-in `sum()` and we don't want to shadow it. Same pattern you'd see in any PySpark job."

> "The key imports for windowing are `window`, `count`, `spark_sum`, `avg`, and `collect_list`. These are the aggregation functions we'll use inside our windows."

### Threshold Configuration (Lines 21-24)

```python
KAFKA_BOOTSTRAP_SERVERS = sys.argv[1] if len(sys.argv) > 1 else "kafka:29092"
ORDER_RATE_THRESHOLD = int(sys.argv[2]) if len(sys.argv) > 2 else 100
NOTIONAL_THRESHOLD = float(sys.argv[3]) if len(sys.argv) > 3 else 1000000
SYMBOL_CONCENTRATION_THRESHOLD = float(sys.argv[4]) if len(sys.argv) > 4 else 0.7
```

> "Thresholds are passed as command-line arguments with sensible defaults. This makes them tunable without code changes."

> "Three thresholds: more than **100 orders in 60 seconds** (rate), more than **$1 million in 60 seconds** (notional exposure), or more than **70% of orders in a single symbol** (concentration). We'll see exactly how each is computed."

**Ask the class:** "If Knight Capital's algorithm was buying and selling 150 stocks at high speed, which of these three thresholds would it trip first?" (Answer: probably all three within seconds, but rate would trip first.)

### Order Schema (Lines 32-41)

```python
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
```

> "This schema must exactly match what the Order Generator produces. Spark uses it to parse the JSON from Kafka. If a field name is wrong or a type doesn't match, you get nulls — no error, just silent data loss. That's a common Spark gotcha."

> "Notice `ts` is a `LongType` — epoch milliseconds. We'll convert this to a timestamp for windowing."

---

## Part 2: Reading from Kafka (Lines 50-64)

```python
def read_orders_stream(spark):
    """Read orders from Kafka - PLAINTEXT, no IAM auth"""
    return spark \
        .readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", "orders.v1") \
        .option("startingOffsets", "latest") \
        .load() \
        .select(
            from_json(col("value").cast("string"), order_schema).alias("order")
        ) \
        .select("order.*") \
        .withColumn("notional", col("qty") * col("price")) \
        .withColumn("event_time", (col("ts") / 1000).cast("timestamp"))
```

Walk through each piece:

> "**`.readStream.format("kafka")`** — this creates a streaming DataFrame that reads from Kafka. Not `read` (batch) but `readStream` (continuous)."

> "**`.option("subscribe", "orders.v1")`** — we subscribe to the orders topic. You could also use `subscribePattern` for multiple topics."

> "**`.option("startingOffsets", "latest")`** — when the job starts for the first time, start from the latest offset. We don't want to process historical orders on startup. In production you might use `earliest` if you need to backfill."

> "**`from_json(col("value").cast("string"), order_schema)`** — Kafka gives us binary key-value pairs. We cast the value to a string, then parse it as JSON using our schema. This is the Spark equivalent of `json.loads()` but it operates on entire columns."

> "**`.select("order.*")`** — flattens the nested struct into top-level columns. After this, we have `order_id`, `ts`, `account_id`, `symbol`, `side`, `qty`, `price`, `strategy` as individual columns."

> "**Two computed columns:**"
> - `notional = qty * price` — the dollar value of the order. 100 shares at $150 = $15,000 notional.
> - `event_time = (ts / 1000).cast("timestamp")` — convert epoch millis to a Spark timestamp. **This is critical** because Spark's `window()` function operates on timestamp columns.

---

## Part 3: The Concentration UDF (Lines 66-74)

```python
@udf(FloatType())
def compute_concentration(symbols):
    """Compute top symbol concentration from collected symbol list."""
    if not symbols:
        return 0.0
    from collections import Counter
    counts = Counter(symbols)
    most_common_count = counts.most_common(1)[0][1]
    return float(most_common_count) / float(len(symbols))
```

> "This is a User Defined Function — a UDF. We need it because Spark SQL doesn't have a built-in 'top frequency ratio' function."

> "It takes a list of symbols — like `['AAPL', 'AAPL', 'AAPL', 'GOOGL', 'TSLA']` — and returns the fraction that the most common symbol represents. In this case: 3 out of 5 = 0.6 = 60% concentration."

> "If an account sends 100 orders and 75 are for AAPL, that's 75% concentration — above our 70% threshold. That could be a broken algorithm hammering one stock."

> "**Performance note:** UDFs are slower than native Spark functions because they serialize data to Python and back. In production, you'd try to express this as native Spark SQL. But for clarity and correctness, a UDF is fine here."

---

## Part 4: Windowed Aggregation (Lines 76-100) — THE KEY FUNCTION

This is the heart of the system. Slow down here.

```python
def compute_risk_signals(orders_df):
    return orders_df \
        .withWatermark("event_time", "60 seconds") \
        .groupBy(
            window(col("event_time"), "60 seconds"),
            col("account_id")
        ) \
        .agg(
            count("*").alias("order_count"),
            spark_sum("notional").alias("total_notional"),
            avg("notional").alias("avg_notional"),
            approx_count_distinct("symbol").alias("unique_symbols"),
            spark_max("symbol").alias("top_symbol"),
            collect_list("symbol").alias("_symbols")
        ) \
        .withColumn("window_start", col("window.start")) \
        .withColumn("window_end", col("window.end")) \
        .withColumn("ts", (unix_timestamp(current_timestamp()) * lit(1000)).cast("long")) \
        .withColumn("top_symbol_share", compute_concentration(col("_symbols"))) \
        .drop("window", "_symbols")
```

Walk through line by line:

### The Watermark (Line 83)

> "**`.withWatermark("event_time", "60 seconds")`** — this tells Spark: 'data can arrive up to 60 seconds late. After that, drop it.' Without a watermark, Spark would keep every window open forever, waiting for late data. Memory would grow unbounded."

> "In practice, this means if an order has a timestamp from 2 minutes ago, and the current watermark has advanced past that window, the order is dropped. This is the tradeoff between completeness and resource usage."

### The GroupBy with Window (Lines 84-86)

> "**`window(col("event_time"), "60 seconds")`** — this is the tumbling window. Every order gets assigned to a 60-second bucket based on its event time. An order at 12:00:45 goes in the 12:00:00-12:01:00 window."

> "**`col("account_id")`** — we group by **both** the window and the account ID. This means we get one aggregated row per account per 60-second window. Account 12345 in the noon window is separate from account 12345 in the 12:01 window, and separate from account 67890 in the noon window."

> "This is the fundamental unit of risk analysis: **one account, one minute.**"

### The Aggregations (Lines 88-95)

> "Inside each window-account bucket, we compute six things:"

| Aggregation | What It Computes | Why |
|---|---|---|
| `count("*")` | Number of orders | Rate detection |
| `spark_sum("notional")` | Total dollar exposure | Exposure detection |
| `avg("notional")` | Average order size | Informational |
| `approx_count_distinct("symbol")` | How many unique symbols | Diversity metric |
| `spark_max("symbol")` | A representative symbol | For the kill reason message |
| `collect_list("symbol")` | All symbols as a list | For concentration UDF |

> "Notice `approx_count_distinct` — not `count_distinct`. The approximate version uses HyperLogLog, which is much more memory-efficient. For our purposes, approximate is fine — we're not billing anyone, we're detecting anomalies."

> "**`collect_list("symbol")`** — this collects every symbol in the window into a Python list. This is what feeds our concentration UDF. It's the most expensive aggregation because it materializes all values, but there's no native Spark function for 'mode frequency ratio.'"

### Post-Aggregation Columns (Lines 96-100)

> "After aggregation, we extract `window_start` and `window_end` from the window struct, add a processing timestamp, compute the concentration from the collected symbol list, and drop the intermediate columns."

> "The result is one row per account per minute with all the risk metrics we need."

---

## Part 5: Threshold Detection (Lines 102-152)

```python
def detect_threshold_breaches(risk_signals_df):
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
```

> "Three boolean columns, one per threshold. Then we filter to rows where **any** threshold is breached. If an account has 50 orders, $500K notional, and 30% concentration — all under threshold — this row is filtered out. No kill command."

> "If an account has 150 orders — above the 100 threshold — this row survives the filter and becomes a kill command."

### Building the Kill Command (Lines 117-152)

```python
    kill_commands = breaches \
        .withColumn("cmd_id", lit(str(uuid.uuid4()))) \
        .withColumn("scope",
                   concat(lit("ACCOUNT:"), col("account_id"))) \
        .withColumn("action", lit("KILL")) \
        .withColumn("triggered_by", lit("spark")) \
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
                   .otherwise(lit("Multiple breaches")))
```

> "Each breach row becomes a kill command with:"
> - **`scope`**: `ACCOUNT:12345` — we kill the account, not the symbol
> - **`action`**: always `KILL` — Spark never unkills
> - **`triggered_by`**: `"spark"` — this distinguishes auto-kills from operator kills
> - **`reason`**: a human-readable string like "Order rate breach: 150 orders in 60s"

> "The `when().when().otherwise()` chain picks the reason for the **first** threshold breached, with priority: rate > notional > concentration. If multiple thresholds are breached, only one reason is reported. The `otherwise` case catches edge conditions."

> "**Important design decision:** Spark kills at the ACCOUNT level, not SYMBOL level. If an account's algorithm is misbehaving, you want to stop the entire account, not just one symbol. The account's human can investigate which strategy went wrong."

---

## Part 6: Writing to Kafka (Lines 154-182)

### Risk Signals Output (Lines 154-167)

```python
def write_risk_signals(risk_signals_df):
    return risk_signals_df \
        .select(
            col("account_id").alias("key"),
            to_json(struct("*")).alias("value")
        ) \
        .writeStream \
        .format("kafka") \
        .option("topic", "risk_signals.v1") \
        .option("checkpointLocation", "/tmp/checkpoint/risk_signals") \
        .outputMode("update") \
        .start()
```

> "Risk signals go to `risk_signals.v1` with `outputMode("update")`. Update mode means: emit a row every time the aggregation for a window-account changes. As new orders arrive in a window, the counts update, and Spark emits the updated row."

### Kill Commands Output (Lines 169-182)

```python
def write_kill_commands(kill_commands_df):
    return kill_commands_df \
        .select(
            col("scope").alias("key"),
            to_json(struct("*")).alias("value")
        ) \
        .writeStream \
        .format("kafka") \
        .option("topic", "killswitch.commands.v1") \
        .option("checkpointLocation", "/tmp/checkpoint/kill_commands") \
        .outputMode("append") \
        .start()
```

> "Kill commands use `outputMode("append")`. Append mode means: emit a row only once, when the window closes and the aggregation is final. This is important — we don't want to emit kill commands on every intermediate update. We wait until the window closes, the aggregation is complete, and **then** decide if the threshold was breached."

> "**This is a critical difference.** Risk signals use `update` (emit frequently for monitoring). Kill commands use `append` (emit once for action). Getting this wrong means either missing detections or flooding the system with duplicate kills."

---

## Part 7: The Main Loop (Lines 184-218)

```python
def main():
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    orders_df = read_orders_stream(spark)
    risk_signals_df = compute_risk_signals(orders_df)
    kill_commands_df = detect_threshold_breaches(risk_signals_df)

    signals_query = write_risk_signals(risk_signals_df)
    commands_query = write_kill_commands(kill_commands_df)

    while True:
        time.sleep(10)
        for q in spark.streams.active:
            if q.exception():
                print(f"Query {q.name} failed: {q.exception()}")
        if not spark.streams.active:
            signals_query = write_risk_signals(risk_signals_df)
            commands_query = write_kill_commands(kill_commands_df)
```

> "The main function is the pipeline assembly. Notice it's **declarative** — we describe the transformations, and Spark manages the execution. `read_orders_stream` returns a streaming DataFrame. `compute_risk_signals` transforms it. `detect_threshold_breaches` filters it. The `write_*` functions start the actual streaming queries."

> "The monitoring loop checks every 10 seconds for query failures. If all queries die — maybe Kafka went down temporarily — it restarts them. This is basic resiliency. In production on EMR, the cluster manager handles this."

> "Two streaming queries run concurrently from the same source: one for risk signals, one for kill commands. Spark optimizes this under the hood — it doesn't read from Kafka twice."

---

## Presenter Notes

**Pacing:** This is the densest section. If you see eyes glazing over, skip the UDF explanation and the output mode discussion. The core message is: "60-second windows per account, three thresholds, kill on breach."

**If someone asks "why 60 seconds?":** It's a tuning parameter. Shorter windows (10s) catch fast-moving anomalies but generate more false positives. Longer windows (5min) smooth out noise but react slower. 60 seconds is a common starting point. Exercise 3 asks students to implement multi-window detection.

**If someone asks "what about false positives?":** Great question. If Spark kills an account that was actually trading normally (just fast), a human reviews and unkills. The cost of a false positive is a brief trading halt. The cost of a false negative (missing a real anomaly) could be millions in losses. The system is intentionally biased toward caution.

**If someone asks "why `append` for kills but `update` for signals?":** Append waits for the window to close (watermark to advance past the window end). This means a kill command reflects the full 60-second picture. Update emits on every micro-batch, giving real-time visibility into accumulating risk. You want certainty for kills, freshness for monitoring.

---

## Timing Check

By the end of this section, you should be at **27 minutes** total. You've covered the most technically dense part of the talk. The remaining sections are shorter and more interactive.
