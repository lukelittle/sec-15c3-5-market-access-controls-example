resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.name_prefix}-${var.environment}"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", { stat = "Sum", label = "Order Generator" }],
            ["...", { stat = "Sum", label = "Kill Switch Aggregator" }],
            ["...", { stat = "Sum", label = "Order Router" }]
          ]
          period = 300
          stat   = "Sum"
          region = data.aws_region.current.name
          title  = "Lambda Invocations"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Lambda", "Errors", { stat = "Sum", label = "Errors" }],
            [".", "Throttles", { stat = "Sum", label = "Throttles" }]
          ]
          period = 300
          stat   = "Sum"
          region = data.aws_region.current.name
          title  = "Lambda Errors & Throttles"
        }
      },
      {
        type = "log"
        properties = {
          query   = "SOURCE '${var.order_generator_log_group}' | fields @timestamp, @message | filter @message like /orders_sent/ | sort @timestamp desc | limit 20"
          region  = data.aws_region.current.name
          title   = "Order Generator Logs"
        }
      },
      {
        type = "log"
        properties = {
          query   = "SOURCE '${var.order_router_log_group}' | fields @timestamp, @message | filter @message like /DROPPED/ | sort @timestamp desc | limit 20"
          region  = data.aws_region.current.name
          title   = "Dropped Orders"
        }
      }
    ]
  })
}

data "aws_region" "current" {}
