resource "aws_msk_serverless_cluster" "main" {
  cluster_name = "${var.name_prefix}-${var.environment}"

  client_authentication {
    sasl {
      iam {
        enabled = true
      }
    }
  }

  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = [data.aws_security_group.msk.id]
  }

  tags = {
    Name = "${var.name_prefix}-${var.environment}-msk"
  }
}

data "aws_security_group" "msk" {
  id = var.vpc_id
  filter {
    name   = "tag:Name"
    values = ["${var.name_prefix}-${var.environment}-msk-sg"]
  }
}

# Note: Topics are created via kafka-topics CLI after cluster is ready
# See tools/create-topics.sh
