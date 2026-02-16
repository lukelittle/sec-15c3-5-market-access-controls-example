# Order Generator Lambda Role
resource "aws_iam_role" "order_generator" {
  name_prefix = "${var.name_prefix}-${var.environment}-order-gen-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = {
    Name = "${var.name_prefix}-${var.environment}-order-generator-role"
  }
}

resource "aws_iam_role_policy" "order_generator" {
  name_prefix = "order-generator-policy-"
  role        = aws_iam_role.order_generator.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:Connect",
          "kafka-cluster:DescribeCluster"
        ]
        Resource = var.msk_cluster_arn
      },
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:CreateTopic",
          "kafka-cluster:DescribeTopic",
          "kafka-cluster:WriteData"
        ]
        Resource = "${replace(var.msk_cluster_arn, ":cluster/", ":topic/")}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = "*"
      }
    ]
  })
}

# Kill Switch Aggregator Lambda Role
resource "aws_iam_role" "killswitch_aggregator" {
  name_prefix = "${var.name_prefix}-${var.environment}-ks-agg-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = {
    Name = "${var.name_prefix}-${var.environment}-killswitch-aggregator-role"
  }
}

resource "aws_iam_role_policy" "killswitch_aggregator" {
  name_prefix = "killswitch-aggregator-policy-"
  role        = aws_iam_role.killswitch_aggregator.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:Connect",
          "kafka-cluster:DescribeCluster"
        ]
        Resource = var.msk_cluster_arn
      },
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:ReadData",
          "kafka-cluster:DescribeTopic",
          "kafka-cluster:DescribeGroup"
        ]
        Resource = [
          "${replace(var.msk_cluster_arn, ":cluster/", ":topic/")}/*",
          "${replace(var.msk_cluster_arn, ":cluster/", ":group/")}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:WriteData"
        ]
        Resource = "${replace(var.msk_cluster_arn, ":cluster/", ":topic/")}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:GetItem"
        ]
        Resource = var.dynamodb_table_arns
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = "*"
      }
    ]
  })
}

# Order Router Lambda Role
resource "aws_iam_role" "order_router" {
  name_prefix = "${var.name_prefix}-${var.environment}-router-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = {
    Name = "${var.name_prefix}-${var.environment}-order-router-role"
  }
}

resource "aws_iam_role_policy" "order_router" {
  name_prefix = "order-router-policy-"
  role        = aws_iam_role.order_router.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:Connect",
          "kafka-cluster:DescribeCluster"
        ]
        Resource = var.msk_cluster_arn
      },
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:ReadData",
          "kafka-cluster:DescribeTopic",
          "kafka-cluster:DescribeGroup"
        ]
        Resource = [
          "${replace(var.msk_cluster_arn, ":cluster/", ":topic/")}/*",
          "${replace(var.msk_cluster_arn, ":cluster/", ":group/")}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:WriteData"
        ]
        Resource = "${replace(var.msk_cluster_arn, ":cluster/", ":topic/")}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query"
        ]
        Resource = var.dynamodb_table_arns
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = "*"
      }
    ]
  })
}

# Operator Console Lambda Role
resource "aws_iam_role" "operator_console" {
  name_prefix = "${var.name_prefix}-${var.environment}-console-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = {
    Name = "${var.name_prefix}-${var.environment}-operator-console-role"
  }
}

resource "aws_iam_role_policy" "operator_console" {
  name_prefix = "operator-console-policy-"
  role        = aws_iam_role.operator_console.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:Connect",
          "kafka-cluster:DescribeCluster"
        ]
        Resource = var.msk_cluster_arn
      },
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:WriteData",
          "kafka-cluster:DescribeTopic"
        ]
        Resource = "${replace(var.msk_cluster_arn, ":cluster/", ":topic/")}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = "*"
      }
    ]
  })
}

# EMR Serverless Execution Role
resource "aws_iam_role" "emr_execution" {
  name_prefix = "${var.name_prefix}-${var.environment}-emr-exec-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "emr-serverless.amazonaws.com"
      }
    }]
  })

  tags = {
    Name = "${var.name_prefix}-${var.environment}-emr-execution-role"
  }
}

resource "aws_iam_role_policy" "emr_execution" {
  name_prefix = "emr-execution-policy-"
  role        = aws_iam_role.emr_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.s3_bucket_arn,
          "${var.s3_bucket_arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = "${var.s3_bucket_arn}/spark-logs/*"
      },
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:Connect",
          "kafka-cluster:DescribeCluster"
        ]
        Resource = var.msk_cluster_arn
      },
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:ReadData",
          "kafka-cluster:WriteData",
          "kafka-cluster:DescribeTopic"
        ]
        Resource = "${replace(var.msk_cluster_arn, ":cluster/", ":topic/")}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "kafka-cluster:AlterGroup",
          "kafka-cluster:DescribeGroup"
        ]
        Resource = "${replace(var.msk_cluster_arn, ":cluster/", ":group/")}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}
