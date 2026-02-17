terraform {
  required_version = ">= 1.6"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Optional: Uncomment for remote state
  # backend "s3" {
  #   bucket         = "your-terraform-state-bucket"
  #   key            = "sec-15c3-5-market-access-controls/dev/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "terraform-state-lock"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "sec-15c3-5-market-access-controls"
      Environment = var.environment
      ManagedBy   = "terraform"
      Purpose     = "education"
    }
  }
}

# VPC and Networking
module "vpc" {
  source = "../../modules/vpc"

  environment      = var.environment
  name_prefix      = var.name_prefix
  vpc_cidr         = var.vpc_cidr
  azs              = var.low_cost_mode ? [data.aws_availability_zones.available.names[0]] : slice(data.aws_availability_zones.available.names, 0, 2)
  low_cost_mode    = var.low_cost_mode
}

# MSK Serverless Cluster
module "msk" {
  source = "../../modules/msk"

  environment   = var.environment
  name_prefix   = var.name_prefix
  vpc_id        = module.vpc.vpc_id
  subnet_ids    = module.vpc.private_subnet_ids
  
  depends_on = [module.vpc]
}

# DynamoDB Tables
module "dynamodb" {
  source = "../../modules/dynamodb"

  environment = var.environment
  name_prefix = var.name_prefix
}

# S3 Bucket for artifacts
module "s3" {
  source = "../../modules/s3"

  environment = var.environment
  name_prefix = var.name_prefix
}

# IAM Roles
module "iam" {
  source = "../../modules/iam"

  environment         = var.environment
  name_prefix         = var.name_prefix
  msk_cluster_arn     = module.msk.cluster_arn
  s3_bucket_arn       = module.s3.bucket_arn
  dynamodb_table_arns = module.dynamodb.table_arns
}

# Lambda Functions
module "lambdas" {
  source = "../../modules/lambdas"

  environment            = var.environment
  name_prefix            = var.name_prefix
  vpc_id                 = module.vpc.vpc_id
  private_subnet_ids     = module.vpc.private_subnet_ids
  msk_bootstrap_brokers  = module.msk.bootstrap_brokers
  dynamodb_audit_table   = module.dynamodb.audit_table_name
  dynamodb_state_table   = module.dynamodb.state_table_name
  
  order_generator_role_arn       = module.iam.order_generator_role_arn
  killswitch_aggregator_role_arn = module.iam.killswitch_aggregator_role_arn
  order_router_role_arn          = module.iam.order_router_role_arn
  operator_console_role_arn      = module.iam.operator_console_role_arn
  
  depends_on = [module.msk, module.vpc]
}

# API Gateway for Operator Console
module "api_gateway" {
  source = "../../modules/api_gateway"

  environment                  = var.environment
  name_prefix                  = var.name_prefix
  operator_console_lambda_arn  = module.lambdas.operator_console_lambda_arn
  operator_console_lambda_name = module.lambdas.operator_console_lambda_name
}

# EMR Serverless for Spark
module "emr_serverless" {
  source = "../../modules/emr_serverless"

  environment           = var.environment
  name_prefix           = var.name_prefix
  s3_bucket_arn         = module.s3.bucket_arn
  s3_bucket_name        = module.s3.bucket_name
  vpc_id                = module.vpc.vpc_id
  subnet_ids            = module.vpc.private_subnet_ids
  msk_bootstrap_brokers = module.msk.bootstrap_brokers
  execution_role_arn    = module.iam.emr_execution_role_arn
  
  # Risk thresholds
  order_rate_threshold_60s    = var.order_rate_threshold_60s
  notional_threshold_60s      = var.notional_threshold_60s
  symbol_concentration_threshold = var.symbol_concentration_threshold
}

# CloudWatch Dashboard
module "cloudwatch" {
  source = "../../modules/cloudwatch"

  environment                    = var.environment
  name_prefix                    = var.name_prefix
  order_generator_log_group      = module.lambdas.order_generator_log_group
  killswitch_aggregator_log_group = module.lambdas.killswitch_aggregator_log_group
  order_router_log_group         = module.lambdas.order_router_log_group
  operator_console_log_group     = module.lambdas.operator_console_log_group
}

data "aws_availability_zones" "available" {
  state = "available"
}
