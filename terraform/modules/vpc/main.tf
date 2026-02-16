resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.name_prefix}-${var.environment}-vpc"
  }
}

resource "aws_subnet" "private" {
  count             = length(var.azs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index)
  availability_zone = var.azs[count.index]

  tags = {
    Name = "${var.name_prefix}-${var.environment}-private-${var.azs[count.index]}"
    Type = "private"
  }
}

resource "aws_subnet" "public" {
  count                   = var.low_cost_mode ? 0 : length(var.azs)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index + 10)
  availability_zone       = var.azs[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.name_prefix}-${var.environment}-public-${var.azs[count.index]}"
    Type = "public"
  }
}

resource "aws_internet_gateway" "main" {
  count  = var.low_cost_mode ? 0 : 1
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.name_prefix}-${var.environment}-igw"
  }
}

# VPC Endpoints for cost optimization (avoid NAT gateway)
resource "aws_vpc_endpoint" "s3" {
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.${data.aws_region.current.name}.s3"
  route_table_ids = [aws_route_table.private.id]

  tags = {
    Name = "${var.name_prefix}-${var.environment}-s3-endpoint"
  }
}

resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.${data.aws_region.current.name}.dynamodb"
  route_table_ids = [aws_route_table.private.id]

  tags = {
    Name = "${var.name_prefix}-${var.environment}-dynamodb-endpoint"
  }
}

# Interface endpoints for CloudWatch Logs
resource "aws_vpc_endpoint" "logs" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.logs"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = {
    Name = "${var.name_prefix}-${var.environment}-logs-endpoint"
  }
}

resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "${var.name_prefix}-${var.environment}-vpc-endpoints-"
  description = "Security group for VPC endpoints"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "HTTPS from VPC"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name = "${var.name_prefix}-${var.environment}-vpc-endpoints-sg"
  }
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.name_prefix}-${var.environment}-private-rt"
  }
}

resource "aws_route_table_association" "private" {
  count          = length(aws_subnet.private)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# Security group for MSK
resource "aws_security_group" "msk" {
  name_prefix = "${var.name_prefix}-${var.environment}-msk-"
  description = "Security group for MSK cluster"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 9098
    to_port     = 9098
    protocol    = "tcp"
    self        = true
    description = "MSK IAM auth"
  }

  ingress {
    from_port       = 9098
    to_port         = 9098
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda.id]
    description     = "MSK from Lambda"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name = "${var.name_prefix}-${var.environment}-msk-sg"
  }
}

# Security group for Lambda functions
resource "aws_security_group" "lambda" {
  name_prefix = "${var.name_prefix}-${var.environment}-lambda-"
  description = "Security group for Lambda functions"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name = "${var.name_prefix}-${var.environment}-lambda-sg"
  }
}

data "aws_region" "current" {}
