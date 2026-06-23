# Security Groups module — implements the three-tier firewall model (design §11.3).
#
# ALB SG       : inbound 443/80 from approved CIDRs → outbound to App SG
# App SG       : inbound only from ALB SG → outbound to AWS services
# Mock SG      : inbound only from App SG (mock tool backends)
# VPC Endpoint SG: HTTPS-only from VPC CIDR (used by interface VPC endpoints)

locals {
  prefix = "${var.project_name}-${var.environment}"
}

# ── ALB security group ─────────────────────────────────────────────────────────
resource "aws_security_group" "alb" {
  name        = "${local.prefix}-alb-sg"
  description = "ALB: inbound HTTPS/HTTP from approved client CIDRs."
  vpc_id      = var.vpc_id

  # HTTPS inbound
  ingress {
    description = "HTTPS from approved client CIDRs"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = var.allowed_ingress_cidrs
  }

  # HTTP inbound — redirected to HTTPS by the listener
  ingress {
    description = "HTTP (redirect to HTTPS)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = var.allowed_ingress_cidrs
  }

  tags = {
    Name = "${local.prefix}-alb-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Allow ALB to reach app tier (separate rule to avoid circular ref)
resource "aws_security_group_rule" "alb_to_app" {
  type                     = "egress"
  description              = "ALB outbound to app tier"
  from_port                = var.app_port
  to_port                  = var.app_port
  protocol                 = "tcp"
  security_group_id        = aws_security_group.alb.id
  source_security_group_id = aws_security_group.app.id
}

# ── App security group ─────────────────────────────────────────────────────────
resource "aws_security_group" "app" {
  name        = "${local.prefix}-app-sg"
  description = "App tier: inbound only from ALB SG; outbound to AWS services and mock backends."
  vpc_id      = var.vpc_id

  # Outbound to AWS managed services (HTTPS to VPC endpoints / internet)
  egress {
    description = "HTTPS to AWS services and external APIs"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.prefix}-app-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Inbound to app from ALB only
resource "aws_security_group_rule" "app_from_alb" {
  type                     = "ingress"
  description              = "App inbound from ALB"
  from_port                = var.app_port
  to_port                  = var.app_port
  protocol                 = "tcp"
  security_group_id        = aws_security_group.app.id
  source_security_group_id = aws_security_group.alb.id
}

# Outbound from app to mock service tier
resource "aws_security_group_rule" "app_to_mock" {
  type                     = "egress"
  description              = "App outbound to mock service tier"
  from_port                = var.mock_service_port
  to_port                  = var.mock_service_port
  protocol                 = "tcp"
  security_group_id        = aws_security_group.app.id
  source_security_group_id = aws_security_group.mock_service.id
}

# ── Mock-service security group ────────────────────────────────────────────────
resource "aws_security_group" "mock_service" {
  name        = "${local.prefix}-mock-sg"
  description = "Mock service backends: inbound only from App SG."
  vpc_id      = var.vpc_id

  # Outbound to AWS managed services
  egress {
    description = "HTTPS to AWS services"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.prefix}-mock-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Inbound to mock services from app tier only
resource "aws_security_group_rule" "mock_from_app" {
  type                     = "ingress"
  description              = "Mock service inbound from app tier"
  from_port                = var.mock_service_port
  to_port                  = var.mock_service_port
  protocol                 = "tcp"
  security_group_id        = aws_security_group.mock_service.id
  source_security_group_id = aws_security_group.app.id
}

# ── VPC endpoint security group ────────────────────────────────────────────────
# Used by all interface VPC endpoints (CloudWatch Logs, Bedrock, SSM, etc.).
resource "aws_security_group" "vpc_endpoint" {
  name        = "${local.prefix}-vpce-sg"
  description = "Interface VPC endpoints: HTTPS only from within the VPC CIDR."
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTPS from VPC CIDR"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    description = "HTTPS to AWS service endpoints"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.prefix}-vpce-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}
