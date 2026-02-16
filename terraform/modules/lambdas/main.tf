# Order Generator Lambda
resource "aws_lambda_function" "order_generator" {
  filename         = "${path.module}/../../../services/order_generator/dist/order_generator.zip"
  function_name    = "${var.name_prefix}-${var.environment}-order-generator"
  role            = var.order_generator_role_arn
  handler         = "handler.lambda_handler"
  runtime         = "python3.11"
  timeout         = 900  # 15 minutes for long-running generation
  memory_size     = 512

  environment {
    variables = {
      MSK_BOOTSTRAP_BROKERS = var.msk_bootstrap_brokers
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [data.aws_security_group.lambda.id]
  }

  tags = {
    Name = "${var.name_prefix}-${var.environment}-order-generator"
  }
}

resource "aws_cloudwatch_log_group" "order_generator" {
  name              = "/aws/lambda/${aws_lambda_function.order_generator.function_name}"
  retention_in_days = 7
}

# Kill Switch Aggregator Lambda
resource "aws_lambda_function" "killswitch_aggregator" {
  filename         = "${path.module}/../../../services/killswitch_aggregator/dist/killswitch_aggregator.zip"
  function_name    = "${var.name_prefix}-${var.environment}-killswitch-aggregator"
  role            = var.killswitch_aggregator_role_arn
  handler         = "handler.lambda_handler"
  runtime         = "python3.11"
  timeout         = 900
  memory_size     = 512

  environment {
    variables = {
      MSK_BOOTSTRAP_BROKERS = var.msk_bootstrap_brokers
      DYNAMODB_STATE_TABLE  = var.dynamodb_state_table
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [data.aws_security_group.lambda.id]
  }

  tags = {
    Name = "${var.name_prefix}-${var.environment}-killswitch-aggregator"
  }
}

resource "aws_cloudwatch_log_group" "killswitch_aggregator" {
  name              = "/aws/lambda/${aws_lambda_function.killswitch_aggregator.function_name}"
  retention_in_days = 7
}

# Order Router Lambda
resource "aws_lambda_function" "order_router" {
  filename         = "${path.module}/../../../services/order_router/dist/order_router.zip"
  function_name    = "${var.name_prefix}-${var.environment}-order-router"
  role            = var.order_router_role_arn
  handler         = "handler.lambda_handler"
  runtime         = "python3.11"
  timeout         = 900
  memory_size     = 1024

  environment {
    variables = {
      MSK_BOOTSTRAP_BROKERS = var.msk_bootstrap_brokers
      DYNAMODB_AUDIT_TABLE  = var.dynamodb_audit_table
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [data.aws_security_group.lambda.id]
  }

  tags = {
    Name = "${var.name_prefix}-${var.environment}-order-router"
  }
}

resource "aws_cloudwatch_log_group" "order_router" {
  name              = "/aws/lambda/${aws_lambda_function.order_router.function_name}"
  retention_in_days = 7
}

# Operator Console Lambda
resource "aws_lambda_function" "operator_console" {
  filename         = "${path.module}/../../../services/operator_console/dist/operator_console.zip"
  function_name    = "${var.name_prefix}-${var.environment}-operator-console"
  role            = var.operator_console_role_arn
  handler         = "handler.lambda_handler"
  runtime         = "python3.11"
  timeout         = 30
  memory_size     = 256

  environment {
    variables = {
      MSK_BOOTSTRAP_BROKERS = var.msk_bootstrap_brokers
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [data.aws_security_group.lambda.id]
  }

  tags = {
    Name = "${var.name_prefix}-${var.environment}-operator-console"
  }
}

resource "aws_cloudwatch_log_group" "operator_console" {
  name              = "/aws/lambda/${aws_lambda_function.operator_console.function_name}"
  retention_in_days = 7
}

data "aws_security_group" "lambda" {
  vpc_id = var.vpc_id
  filter {
    name   = "tag:Name"
    values = ["${var.name_prefix}-${var.environment}-lambda-sg"]
  }
}
