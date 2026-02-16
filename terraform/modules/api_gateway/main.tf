resource "aws_apigatewayv2_api" "operator_console" {
  name          = "${var.name_prefix}-${var.environment}-operator-console"
  protocol_type = "HTTP"
  
  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["content-type"]
  }

  tags = {
    Name = "${var.name_prefix}-${var.environment}-operator-console-api"
  }
}

resource "aws_apigatewayv2_integration" "operator_console" {
  api_id           = aws_apigatewayv2_api.operator_console.id
  integration_type = "AWS_PROXY"
  integration_uri  = var.operator_console_lambda_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "kill" {
  api_id    = aws_apigatewayv2_api.operator_console.id
  route_key = "POST /kill"
  target    = "integrations/${aws_apigatewayv2_integration.operator_console.id}"
}

resource "aws_apigatewayv2_route" "unkill" {
  api_id    = aws_apigatewayv2_api.operator_console.id
  route_key = "POST /unkill"
  target    = "integrations/${aws_apigatewayv2_integration.operator_console.id}"
}

resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.operator_console.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.operator_console.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.operator_console.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }
}

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.name_prefix}-${var.environment}-operator-console"
  retention_in_days = 7
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.operator_console_lambda_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.operator_console.execution_arn}/*/*"
}
