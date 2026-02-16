resource "aws_dynamodb_table" "audit_index" {
  name         = "${var.name_prefix}-${var.environment}-audit-index"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "order_id"
  range_key    = "ts"

  attribute {
    name = "order_id"
    type = "S"
  }

  attribute {
    name = "ts"
    type = "N"
  }

  attribute {
    name = "account_id"
    type = "S"
  }

  global_secondary_index {
    name            = "account-index"
    hash_key        = "account_id"
    range_key       = "ts"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = false # Enable for production
  }

  tags = {
    Name = "${var.name_prefix}-${var.environment}-audit-index"
  }
}

resource "aws_dynamodb_table" "state_cache" {
  name         = "${var.name_prefix}-${var.environment}-state-cache"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "scope"

  attribute {
    name = "scope"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = false # Enable for production
  }

  tags = {
    Name = "${var.name_prefix}-${var.environment}-state-cache"
  }
}
