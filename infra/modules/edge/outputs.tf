output "alb_arn" {
  description = "ARN of the Application Load Balancer."
  value       = aws_lb.main.arn
}

output "alb_dns_name" {
  description = "DNS name of the ALB (use this as the API endpoint if no custom domain)."
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "Canonical hosted zone ID of the ALB (for Route53 alias records)."
  value       = aws_lb.main.zone_id
}

output "app_target_group_arn" {
  description = "ARN of the application target group."
  value       = aws_lb_target_group.app.arn
}

output "https_listener_arn" {
  description = "ARN of the HTTPS listener. Null when enable_ssl = false."
  value       = var.enable_ssl ? aws_lb_listener.https[0].arn : null
}

output "certificate_arn" {
  description = "ARN of the ACM certificate after validation. Null when enable_ssl = false."
  value       = var.enable_ssl ? aws_acm_certificate_validation.main[0].certificate_arn : null
}
