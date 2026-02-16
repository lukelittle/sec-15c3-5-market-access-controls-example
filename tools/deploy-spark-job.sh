#!/bin/bash
set -e

echo "Deploying Spark job to EMR Serverless..."

# Get outputs from Terraform
cd terraform/envs/dev
export EMR_APP_ID=$(terraform output -raw emr_application_id)
export EMR_ROLE_ARN=$(terraform output -raw emr_execution_role_arn)
export S3_BUCKET=$(terraform output -raw s3_bucket_name)
export MSK_BOOTSTRAP=$(terraform output -raw msk_bootstrap_brokers)
cd ../../..

echo "EMR Application ID: $EMR_APP_ID"
echo "S3 Bucket: $S3_BUCKET"

# Upload Spark job to S3
echo "Uploading Spark job to S3..."
aws s3 cp spark/risk_job/risk_detector.py \
  s3://$S3_BUCKET/spark-jobs/risk_detector.py

echo "✓ Spark job uploaded"

# Get thresholds from Terraform variables
ORDER_RATE_THRESHOLD=${ORDER_RATE_THRESHOLD:-100}
NOTIONAL_THRESHOLD=${NOTIONAL_THRESHOLD:-1000000}
SYMBOL_CONCENTRATION_THRESHOLD=${SYMBOL_CONCENTRATION_THRESHOLD:-0.7}

echo ""
echo "Starting Spark job with thresholds:"
echo "  Order rate: $ORDER_RATE_THRESHOLD orders/60s"
echo "  Notional: \$$NOTIONAL_THRESHOLD/60s"
echo "  Symbol concentration: $SYMBOL_CONCENTRATION_THRESHOLD"
echo ""

# Start Spark job
JOB_RUN_ID=$(aws emr-serverless start-job-run \
  --application-id $EMR_APP_ID \
  --execution-role-arn $EMR_ROLE_ARN \
  --job-driver '{
    "sparkSubmit": {
      "entryPoint": "s3://'$S3_BUCKET'/spark-jobs/risk_detector.py",
      "entryPointArguments": [
        "'$MSK_BOOTSTRAP'",
        "'$ORDER_RATE_THRESHOLD'",
        "'$NOTIONAL_THRESHOLD'",
        "'$SYMBOL_CONCENTRATION_THRESHOLD'"
      ],
      "sparkSubmitParameters": "--conf spark.executor.cores=2 --conf spark.executor.memory=4g --conf spark.driver.cores=2 --conf spark.driver.memory=4g --conf spark.jars.packages=org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,software.amazon.msk:aws-msk-iam-auth:2.0.0"
    }
  }' \
  --configuration-overrides '{
    "monitoringConfiguration": {
      "s3MonitoringConfiguration": {
        "logUri": "s3://'$S3_BUCKET'/spark-logs/"
      }
    }
  }' \
  --query 'jobRunId' \
  --output text)

echo "✓ Spark job started"
echo ""
echo "Job Run ID: $JOB_RUN_ID"
echo ""
echo "Monitor job status:"
echo "  aws emr-serverless get-job-run --application-id $EMR_APP_ID --job-run-id $JOB_RUN_ID"
echo ""
echo "View logs:"
echo "  aws s3 ls s3://$S3_BUCKET/spark-logs/$EMR_APP_ID/jobs/$JOB_RUN_ID/"
echo ""
echo "Stream logs (once available):"
echo "  aws s3 cp s3://$S3_BUCKET/spark-logs/$EMR_APP_ID/jobs/$JOB_RUN_ID/SPARK_DRIVER/stdout.gz - | gunzip"
