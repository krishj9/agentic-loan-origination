# VPC Endpoints module — reduces public egress for internal workloads (design §11.4).
#
# Gateway endpoints (free, route-table–based):
#   • S3
#
# Interface endpoints (ENI-based, incur hourly cost):
#   • CloudWatch Logs  — structured log delivery without internet egress
#   • Bedrock Runtime  — model invocations from private subnets
#   • SSM              — parameter reads from private subnets (AgentCore outputs)
#
# Each interface endpoint uses the vpc_endpoint_sg (HTTPS only from VPC CIDR).

locals {
  prefix = "${var.project_name}-${var.environment}"
}

# ── S3 gateway endpoint ────────────────────────────────────────────────────────
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = var.private_route_table_ids

  tags = {
    Name = "${local.prefix}-s3-endpoint"
  }
}

# ── CloudWatch Logs interface endpoint ────────────────────────────────────────
resource "aws_vpc_endpoint" "cloudwatch_logs" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.region}.logs"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [var.vpc_endpoint_sg_id]
  private_dns_enabled = true

  tags = {
    Name = "${local.prefix}-cwlogs-endpoint"
  }
}

# ── Bedrock Runtime interface endpoint ────────────────────────────────────────
resource "aws_vpc_endpoint" "bedrock_runtime" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.region}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [var.vpc_endpoint_sg_id]
  private_dns_enabled = true

  tags = {
    Name = "${local.prefix}-bedrock-runtime-endpoint"
  }
}

# ── SSM interface endpoint ─────────────────────────────────────────────────────
resource "aws_vpc_endpoint" "ssm" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.region}.ssm"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnet_ids
  security_group_ids  = [var.vpc_endpoint_sg_id]
  private_dns_enabled = true

  tags = {
    Name = "${local.prefix}-ssm-endpoint"
  }
}
