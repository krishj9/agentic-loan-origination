# Edge module — Application Load Balancer, ACM TLS certificate, and listeners.
#
# TLS termination occurs at the ALB (design §3.2, requirements §4.2).
# HTTP:80 is permanently redirected to HTTPS:443.
#
# ACM certificate DNS validation:
#   • If route53_zone_id is provided, DNS CNAME records are created automatically.
#   • If empty, the certificate is requested but validation records must be added
#     manually; the ALB listener will wait until the cert reaches ISSUED state.
#
# For a demo without a registered domain, set `domain_name` to a subdomain you
# control and provide the Route53 zone ID, or manually validate via DNS/email.

locals {
  prefix = "${var.project_name}-${var.environment}"
}

# ── ACM certificate ────────────────────────────────────────────────────────────
resource "aws_acm_certificate" "main" {
  domain_name       = var.domain_name
  validation_method = "DNS"

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

# ── Route53 DNS validation records (optional) ──────────────────────────────────
resource "aws_route53_record" "cert_validation" {
  for_each = var.route53_zone_id != "" ? {
    for dvo in aws_acm_certificate.main.domain_validation_options :
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

# ── Certificate validation waiter ─────────────────────────────────────────────
resource "aws_acm_certificate_validation" "main" {
  certificate_arn = aws_acm_certificate.main.arn

  validation_record_fqdns = var.route53_zone_id != "" ? [
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

  # Enable access logs for ALB request auditing.
  access_logs {
    bucket  = var.access_logs_bucket
    prefix  = "${local.prefix}-alb"
    enabled = var.access_logs_bucket != ""
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

# ── HTTPS listener ─────────────────────────────────────────────────────────────
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"

  # TLS 1.2+ only; TLS 1.3 preferred.
  ssl_policy      = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn = aws_acm_certificate_validation.main.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }

  tags = {
    Name = "${local.prefix}-https-listener"
  }
}

# ── HTTP → HTTPS redirect listener ────────────────────────────────────────────
resource "aws_lb_listener" "http_redirect" {
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

# ── Optional Route53 A record pointing the domain at the ALB ──────────────────
resource "aws_route53_record" "alb" {
  count = var.route53_zone_id != "" ? 1 : 0

  zone_id = var.route53_zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}
