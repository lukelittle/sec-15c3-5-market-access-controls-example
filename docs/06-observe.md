# Observability and Monitoring

Guide to observing and debugging the streaming risk controls system.

## Overview

The system provides multiple layers of observability:
- **Kafka Topics**: Real-time event streams
- **CloudWatch Logs**: Detailed execution logs
- **CloudWatch Metrics**: Performance metrics
- **CloudWatch Dashboard**: Visual overview
- **DynamoDB**: Queryable audit trail

## Kafka Topics (Real-Time)

### Consuming Topics

Use the provided script:
```bash
./tools/tail-topic.sh <topic-name>
```

Or use kcat directly:
```bash
kcat -C -b $MSK_BOOTSTRAP -t orders.v1 \
  -f 'Key: %k\nValue: %s\nPartition: %p\nOffset: %o\n---\n'
```

### Topic Monitoring

**Check topic lag**:
```bash
kafka-consumer-groups --bootstrap-server $MSK_BOOTSTRAP \
  --describe --group order-router
```

**Count messages**:
```bash
kafka-run-class kafka.tools.GetOffsetShell \
  --broker-list $MSK_BOOTSTRAP \
  --topic orders.v1 \
  --time -1
```

**Check compaction status**:
```bash
kafka-topics --bootstrap-server $MSK_BOOTSTRAP \
  --describe --topic killswitch.state.v1
```

## CloudWatch Logs

### Log Groups

Each Lambda has a dedicated log group:
- `/aws/lambda/streaming-risk-dev-order-generator`
- `/aws/lambda/streaming-risk-dev-killswitch-aggregator`
- `/aws/lambda/streaming-risk-dev-order-router`
- `/aws/lambda/streaming-risk-dev-operator-console`

### Tailing Logs

```bash
# Real-time tail
aws logs tail /aws/lambda/streaming-risk-dev-order-generator --follow

# Last 10 minutes
aws logs tail /aws/lambda/streaming-risk-dev-order-generator \
  --since 10m

# Filter for errors
aws logs tail /aws/lambda/streaming-risk-dev-order-generator \
  --filter-pattern "ERROR"
```

### CloudWatch Insights Queries

**Order generation rate**:
```sql
fields @timestamp, @message
| filter @message like /orders_sent/
| parse @message "orders_sent: *" as count
| stats sum(count) as total_orders by bin(5m)
```

**Dropped orders**:
```sql
fields @timestamp, @message
| filter @message like /DROPPED/
| parse @message "DROPPED order * : *" as order_id, reason
| stats count() by reason
```

**Lambda performance**:
```sql
fields @timestamp, @duration, @billedDuration, @memorySize, @maxMemoryUsed
| filter @type = "REPORT"
| stats avg(@duration), max(@duration), pct(@duration, 99) by bin(5m)
```

**Kill switch activations**:
```sql
fields @timestamp, @message
| filter @message like /KILL/
| parse @message "scope: *, action: *" as scope, action
| stats count() by scope, action
```

## CloudWatch Metrics

### Lambda Metrics

**Invocations**:
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=streaming-risk-dev-order-generator \
  --start-time 2024-03-15T00:00:00Z \
  --end-time 2024-03-15T23:59:59Z \
  --period 300 \
  --statistics Sum
```

**Errors**:
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=streaming-risk-dev-order-router \
  --start-time 2024-03-15T00:00:00Z \
  --end-time 2024-03-15T23:59:59Z \
  --period 300 \
  --statistics Sum
```

**Duration (latency)**:
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=streaming-risk-dev-order-router \
  --start-time 2024-03-15T00:00:00Z \
  --end-time 2024-03-15T23:59:59Z \
  --period 300 \
  --statistics Average,Maximum
```

### Custom Metrics (Optional)

Add custom metrics to Lambda:
```python
import boto3

cloudwatch = boto3.client('cloudwatch')

def publish_metric(metric_name, value, unit='Count'):
    cloudwatch.put_metric_data(
        Namespace='StreamingRiskControls',
        MetricData=[{
            'MetricName': metric_name,
            'Value': value,
            'Unit': unit,
            'Dimensions': [
                {'Name': 'Environment', 'Value': 'dev'},
                {'Name': 'Service', 'Value': 'order-router'}
            ]
        }]
    )

# Usage
publish_metric('OrdersDropped', dropped_count)
publish_metric('OrderRate', orders_per_second, 'Count/Second')
```

## CloudWatch Dashboard

Access the pre-built dashboard:
```bash
cd terraform/envs/dev
terraform output cloudwatch_dashboard_url
```

Or create custom dashboard:
```json
{
  "widgets": [
    {
      "type": "metric",
      "properties": {
        "metrics": [
          ["AWS/Lambda", "Invocations", {"stat": "Sum"}]
        ],
        "period": 300,
        "stat": "Sum",
        "region": "us-east-1",
        "title": "Lambda Invocations"
      }
    }
  ]
}
```

## DynamoDB Queries

### Audit Trail Queries

**Query by order ID**:
```bash
aws dynamodb query \
  --table-name streaming-risk-dev-audit-index \
  --key-condition-expression "order_id = :oid" \
  --expression-attribute-values '{":oid":{"S":"<order-id>"}}'
```

**Query by account (using GSI)**:
```bash
aws dynamodb query \
  --table-name streaming-risk-dev-audit-index \
  --index-name account-index \
  --key-condition-expression "account_id = :aid" \
  --expression-attribute-values '{":aid":{"S":"12345"}}'
```

**Scan for dropped orders**:
```bash
aws dynamodb scan \
  --table-name streaming-risk-dev-audit-index \
  --filter-expression "decision = :dec" \
  --expression-attribute-values '{":dec":{"S":"DROP"}}' \
  --limit 100
```

### Kill State Cache

**Get current state for scope**:
```bash
aws dynamodb get-item \
  --table-name streaming-risk-dev-state-cache \
  --key '{"scope":{"S":"ACCOUNT:12345"}}'
```

**Scan all kill states**:
```bash
aws dynamodb scan \
  --table-name streaming-risk-dev-state-cache
```

## Spark Job Monitoring

### Job Status

```bash
# List job runs
aws emr-serverless list-job-runs \
  --application-id $EMR_APP_ID

# Get specific job run
aws emr-serverless get-job-run \
  --application-id $EMR_APP_ID \
  --job-run-id <job-run-id>
```

### Spark Logs

```bash
# List log files
aws s3 ls s3://$S3_BUCKET/spark-logs/$EMR_APP_ID/jobs/<job-run-id>/

# View driver stdout
aws s3 cp s3://$S3_BUCKET/spark-logs/$EMR_APP_ID/jobs/<job-run-id>/SPARK_DRIVER/stdout.gz - | gunzip

# View driver stderr
aws s3 cp s3://$S3_BUCKET/spark-logs/$EMR_APP_ID/jobs/<job-run-id>/SPARK_DRIVER/stderr.gz - | gunzip

# View executor logs
aws s3 ls s3://$S3_BUCKET/spark-logs/$EMR_APP_ID/jobs/<job-run-id>/executors/
```

### Spark UI (Optional)

Enable Spark History Server for UI access (not included in demo).

## Correlation ID Tracing

Every event includes a correlation ID for end-to-end tracing.

**Trace a kill command**:
1. Find kill command in `killswitch.commands.v1`
2. Note `corr_id`
3. Search for same `corr_id` in:
   - `killswitch.state.v1` (state update)
   - `audit.v1` (enforcement decisions)
   - CloudWatch Logs (Lambda execution)

**Example**:
```bash
# Get kill command
./tools/tail-topic.sh killswitch.commands.v1 | grep "corr_id"

# Search audit trail
./tools/tail-topic.sh audit.v1 | grep "<corr-id>"

# Search CloudWatch Logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/streaming-risk-dev-order-router \
  --filter-pattern "<corr-id>"
```

## Performance Monitoring

### Latency Tracking

**Order router latency**:
```sql
-- CloudWatch Insights
fields @timestamp, @duration
| filter @type = "REPORT"
| stats avg(@duration) as avg_ms, pct(@duration, 99) as p99_ms by bin(5m)
```

**End-to-end latency** (order to audit):
- Requires custom instrumentation
- Add timestamps at each stage
- Calculate delta in audit event

### Throughput Monitoring

**Orders per second**:
```bash
# Count messages in time window
kafka-run-class kafka.tools.GetOffsetShell \
  --broker-list $MSK_BOOTSTRAP \
  --topic orders.v1 \
  --time -1

# Calculate rate: (offset_now - offset_before) / seconds
```

**Dropped order rate**:
```sql
-- CloudWatch Insights
fields @timestamp, @message
| filter @message like /decision/
| parse @message "decision: *" as decision
| stats count() by decision, bin(1m)
```

## Alerting (Optional)

### CloudWatch Alarms

**High error rate**:
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name high-lambda-errors \
  --alarm-description "Alert when Lambda error rate is high" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=streaming-risk-dev-order-router
```

**High drop rate**:
```bash
# Requires custom metric
aws cloudwatch put-metric-alarm \
  --alarm-name high-drop-rate \
  --metric-name OrdersDropped \
  --namespace StreamingRiskControls \
  --statistic Sum \
  --period 60 \
  --evaluation-periods 1 \
  --threshold 100 \
  --comparison-operator GreaterThanThreshold
```

### SNS Notifications

```bash
# Create SNS topic
aws sns create-topic --name streaming-risk-alerts

# Subscribe email
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789012:streaming-risk-alerts \
  --protocol email \
  --notification-endpoint your-email@example.com

# Add to alarm
aws cloudwatch put-metric-alarm \
  --alarm-name high-lambda-errors \
  --alarm-actions arn:aws:sns:us-east-1:123456789012:streaming-risk-alerts \
  ...
```

## Debugging Workflows

### Order Not Flowing

1. Check order generator is running
2. Verify orders in `orders.v1` topic
3. Check order router is consuming
4. Look for errors in CloudWatch Logs
5. Verify security groups allow Kafka access

### Kill Switch Not Triggering

1. Verify Spark job is running
2. Check orders are flowing (input to Spark)
3. Verify risk signals in `risk_signals.v1`
4. Check thresholds are set correctly
5. Look for Spark errors in S3 logs

### Orders Not Dropped

1. Verify kill command in `killswitch.commands.v1`
2. Check kill state in `killswitch.state.v1`
3. Verify order router is consuming state
4. Check audit trail for DROP decisions
5. Look for router errors in CloudWatch Logs

## Best Practices

1. **Use correlation IDs** for tracing
2. **Log structured data** (JSON) for easy parsing
3. **Monitor key metrics** (latency, throughput, errors)
4. **Set up alerts** for critical failures
5. **Retain logs** for compliance (7+ years for SEC)
6. **Use CloudWatch Insights** for ad-hoc queries
7. **Archive to S3** for long-term storage

## Tools Summary

| Tool | Use Case | Command |
|------|----------|---------|
| kcat | Consume Kafka topics | `kcat -C -b $MSK_BOOTSTRAP -t <topic>` |
| AWS CLI | Query CloudWatch/DynamoDB | `aws logs tail <log-group>` |
| CloudWatch Insights | Log analysis | Use AWS Console |
| CloudWatch Dashboard | Visual monitoring | Use AWS Console |
| Terraform | Infrastructure state | `terraform show` |

## Next Steps

- [05-exercises.md](05-exercises.md): Build monitoring dashboard
- [06-troubleshooting.md](06-troubleshooting.md): Debug common issues
- [08-security-notes.md](08-security-notes.md): Security monitoring
