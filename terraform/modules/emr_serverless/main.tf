resource "aws_emrserverless_application" "spark" {
  name          = "${var.name_prefix}-${var.environment}-risk-detector"
  release_label = "emr-7.0.0"
  type          = "spark"

  initial_capacity {
    initial_capacity_type = "Driver"

    initial_capacity_config {
      worker_count = 1
      worker_configuration {
        cpu    = "2 vCPU"
        memory = "4 GB"
      }
    }
  }

  initial_capacity {
    initial_capacity_type = "Executor"

    initial_capacity_config {
      worker_count = 2
      worker_configuration {
        cpu    = "4 vCPU"
        memory = "8 GB"
      }
    }
  }

  maximum_capacity {
    cpu    = "16 vCPU"
    memory = "32 GB"
  }

  auto_start_configuration {
    enabled = true
  }

  auto_stop_configuration {
    enabled              = true
    idle_timeout_minutes = 15
  }

  network_configuration {
    subnet_ids         = var.subnet_ids
    security_group_ids = [aws_security_group.emr.id]
  }

  tags = {
    Name = "${var.name_prefix}-${var.environment}-risk-detector"
  }
}

resource "aws_security_group" "emr" {
  name_prefix = "${var.name_prefix}-${var.environment}-emr-"
  description = "Security group for EMR Serverless"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name = "${var.name_prefix}-${var.environment}-emr-sg"
  }
}

# Upload Spark job to S3
resource "aws_s3_object" "spark_job" {
  bucket = var.s3_bucket_name
  key    = "spark-jobs/risk_detector.py"
  source = "${path.module}/../../../spark/risk_job/risk_detector.py"
  etag   = filemd5("${path.module}/../../../spark/risk_job/risk_detector.py")
}

# Create a script to run the Spark job
resource "local_file" "run_spark_job" {
  filename = "${path.module}/../../../tools/run-spark-job.sh"
  content  = <<-EOF
    #!/bin/bash
    set -e
    
    APPLICATION_ID="${aws_emrserverless_application.spark.id}"
    EXECUTION_ROLE_ARN="${var.execution_role_arn}"
    S3_BUCKET="${var.s3_bucket_name}"
    BOOTSTRAP_BROKERS="${var.msk_bootstrap_brokers}"
    
    echo "Starting Spark job on EMR Serverless..."
    echo "Application ID: $APPLICATION_ID"
    
    JOB_RUN_ID=$(aws emr-serverless start-job-run \
      --application-id $APPLICATION_ID \
      --execution-role-arn $EXECUTION_ROLE_ARN \
      --job-driver '{
        "sparkSubmit": {
          "entryPoint": "s3://'$S3_BUCKET'/spark-jobs/risk_detector.py",
          "entryPointArguments": [
            "'$BOOTSTRAP_BROKERS'",
            "${var.order_rate_threshold_60s}",
            "${var.notional_threshold_60s}",
            "${var.symbol_concentration_threshold}"
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
    
    echo "Job started with ID: $JOB_RUN_ID"
    echo ""
    echo "Monitor job status:"
    echo "  aws emr-serverless get-job-run --application-id $APPLICATION_ID --job-run-id $JOB_RUN_ID"
    echo ""
    echo "View logs:"
    echo "  aws s3 ls s3://$S3_BUCKET/spark-logs/$APPLICATION_ID/jobs/$JOB_RUN_ID/"
  EOF
  
  file_permission = "0755"
}
