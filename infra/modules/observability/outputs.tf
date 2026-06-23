output "app_log_group_name" {
  description = "CloudWatch log group name for application logs."
  value       = aws_cloudwatch_log_group.app.name
}

output "app_log_group_arn" {
  description = "ARN of the application log group."
  value       = aws_cloudwatch_log_group.app.arn
}

output "auth_log_group_name" {
  description = "CloudWatch log group name for authentication logs."
  value       = aws_cloudwatch_log_group.auth.name
}

output "auth_log_group_arn" {
  description = "ARN of the authentication log group."
  value       = aws_cloudwatch_log_group.auth.arn
}

output "replay_log_group_name" {
  description = "CloudWatch log group name for evaluation replay logs."
  value       = aws_cloudwatch_log_group.replay.name
}

output "log_group_prefix" {
  description = "Common prefix for all project log groups; pass to the IAM module."
  value       = "/${var.project_name}/${var.environment}"
}

output "log_group_arns" {
  description = "List of all project log group ARNs."
  value = [
    aws_cloudwatch_log_group.app.arn,
    aws_cloudwatch_log_group.auth.arn,
    aws_cloudwatch_log_group.replay.arn,
  ]
}

output "alarms_sns_topic_arn" {
  description = "ARN of the SNS topic receiving alarm notifications."
  value       = aws_sns_topic.alarms.arn
}

output "dashboard_name" {
  description = "Name of the CloudWatch dashboard."
  value       = aws_cloudwatch_dashboard.main.dashboard_name
}

# ── P6-T10 new alarm outputs ──────────────────────────────────────────────────

output "drift_alarm_arn" {
  description = "ARN of the drift events spike CloudWatch alarm."
  value       = aws_cloudwatch_metric_alarm.drift_spike.arn
}

output "accuracy_alarm_arn" {
  description = "ARN of the golden-case accuracy drop CloudWatch alarm."
  value       = aws_cloudwatch_metric_alarm.accuracy_drop.arn
}
