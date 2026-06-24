# Edge module — Application Load Balancer, optional ACM TLS certificate, and listeners.
#
# SSL mode (enable_ssl = true):
#   • ACM certificate is created for domain_name with DNS validation.
#   • HTTPS listener on port 443 forwards traffic to the application target group.
#   • HTTP listener on port 80 issues a 301 redirect to HTTPS.
#   • If route53_zone_id is provided, DNS CNAME records and an ALB alias A record
#     are created automatically; otherwise validate DNS records manually.
#
# Plain HTTP mode (enable_ssl = false, default):
#   • No ACM certificate is created; domain_name is not required.
#   • HTTP listener on port 80 forwards traffic to the application target group.
#   • Access the application via the ALB DNS name output.

locals {
  prefix = "${var.project_name}-${var.environment}"
}

# ── ACM certificate (SSL only) ─────────────────────────────────────────────────
resource "aws_acm_certificate" "main" {
  count = var.enable_ssl ? 1 : 0

  domain_name               = var.domain_name
  validation_method         = "DNS"
  subject_alternative_names = var.subject_alternative_names

  lifecycle {
    # Ensure a new cert is issued before the old one is destroyed (zero-downtime
    # replacement when domain names change).
    create_before_destroy = true
  }

  tags = {
    Name = "${local.prefix}-cert"
  }
}

# ── Route53 DNS validation records (SSL + route53_zone_id only) ────────────────
resource "aws_route53_record" "cert_validation" {
  for_each = (var.enable_ssl && var.route53_zone_id != "") ? {
    for dvo in aws_acm_certificate.main[0].domain_validation_options :
    dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  } : {}

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = var.route53_zone_id
}

# ── Certificate validation waiter (SSL only) ───────────────────────────────────
resource "aws_acm_certificate_validation" "main" {
  count = var.enable_ssl ? 1 : 0

  certificate_arn = aws_acm_certificate.main[0].arn

  validation_record_fqdns = (var.enable_ssl && var.route53_zone_id != "") ? [
    for record in aws_route53_record.cert_validation : record.fqdn
  ] : []
}

# ── Application Load Balancer ──────────────────────────────────────────────────
resource "aws_lb" "main" {
  name               = "${local.prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_sg_id]
  subnets            = var.public_subnet_ids

  # Omit the block entirely when no bucket is provided to avoid an AWS provider
  # bug where planning with enabled=false and an empty bucket string produces
  # an inconsistent final plan when the bucket becomes known during apply.
  dynamic "access_logs" {
    for_each = var.access_logs_bucket != "" ? [var.access_logs_bucket] : []
    content {
      bucket  = access_logs.value
      prefix  = "${local.prefix}-alb"
      enabled = true
    }
  }

  # Drop invalid HTTP headers for security hardening.
  drop_invalid_header_fields = true

  tags = {
    Name = "${local.prefix}-alb"
  }
}

# ── Target group ───────────────────────────────────────────────────────────────
resource "aws_lb_target_group" "app" {
  name        = "${local.prefix}-app-tg"
  port        = var.app_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = var.health_check_path
    port                = "traffic-port"
    protocol            = "HTTP"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }

  tags = {
    Name = "${local.prefix}-app-tg"
  }
}

# ── HTTPS listener (SSL only) ──────────────────────────────────────────────────
resource "aws_lb_listener" "https" {
  count = var.enable_ssl ? 1 : 0

  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"

  # TLS 1.2+ only; TLS 1.3 preferred.
  ssl_policy      = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn = aws_acm_certificate_validation.main[0].certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }

  tags = {
    Name = "${local.prefix}-https-listener"
  }
}

# ── HTTP → HTTPS redirect listener (SSL only) ──────────────────────────────────
resource "aws_lb_listener" "http_redirect" {
  count = var.enable_ssl ? 1 : 0

  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }

  tags = {
    Name = "${local.prefix}-http-redirect"
  }
}

# ── HTTP forward listener (plain HTTP mode only) ───────────────────────────────
resource "aws_lb_listener" "http" {
  count = var.enable_ssl ? 0 : 1

  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }

  tags = {
    Name = "${local.prefix}-http-listener"
  }
}

# ── Optional Route53 A record pointing the domain at the ALB (SSL only) ────────
resource "aws_route53_record" "alb" {
  count = (var.enable_ssl && var.route53_zone_id != "") ? 1 : 0

  zone_id = var.route53_zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}
