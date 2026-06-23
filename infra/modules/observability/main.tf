# Observability module — CloudWatch log groups, metric filters, dashboard, and alarms.
#
# Log groups (requirements §7.1, design §10.1):
#   /loan-origination/demo/app     — application + agent + tool traces
#   /loan-origination/demo/auth    — authentication attempts and failures
#   /loan-origination/demo/replay  — evaluation harness replay runs
#
# Metric filter: auth failures → custom metric for alerting.
# Dashboard: auth failures, accuracy, drift, application error rate.
# Alarms: auth failure rate, application error rate.

locals {
  prefix    = "${var.project_name}-${var.environment}"
  log_base  = "/${var.project_name}/${var.environment}"
  namespace = "${var.project_name}/${var.environment}"
}

# ── Log groups ────────────────────────────────────────────────────────────────
resource "aws_cloudwatch_log_group" "app" {
  name              = "${local.log_base}/app"
  retention_in_days = var.log_retention_days

  tags = {
    Name    = "${local.prefix}-app-logs"
    LogType = "application"
  }
}

resource "aws_cloudwatch_log_group" "auth" {
  name              = "${local.log_base}/auth"
  retention_in_days = var.log_retention_days

  tags = {
    Name    = "${local.prefix}-auth-logs"
    LogType = "authentication"
  }
}

resource "aws_cloudwatch_log_group" "replay" {
  name              = "${local.log_base}/replay"
  retention_in_days = var.log_retention_days

  tags = {
    Name    = "${local.prefix}-replay-logs"
    LogType = "evaluation"
  }
}

# ── Metric filter: authentication failures ────────────────────────────────────
resource "aws_cloudwatch_log_metric_filter" "auth_failures" {
  name           = "${local.prefix}-auth-failures"
  pattern        = "{ $.level = \"ERROR\" && $.event_type = \"AUTH_FAILURE\" }"
  log_group_name = aws_cloudwatch_log_group.auth.name

  metric_transformation {
    name          = "AuthFailures"
    namespace     = local.namespace
    value         = "1"
    unit          = "Count"
    default_value = "0"
  }
}

# ── Metric filter: application errors ─────────────────────────────────────────
resource "aws_cloudwatch_log_metric_filter" "app_errors" {
  name           = "${local.prefix}-app-errors"
  pattern        = "{ $.level = \"ERROR\" }"
  log_group_name = aws_cloudwatch_log_group.app.name

  metric_transformation {
    name          = "AppErrors"
    namespace     = local.namespace
    value         = "1"
    unit          = "Count"
    default_value = "0"
  }
}

# ── Metric filter: drift detection events ─────────────────────────────────────
resource "aws_cloudwatch_log_metric_filter" "drift_events" {
  name           = "${local.prefix}-drift-events"
  pattern        = "{ $.event_type = \"DRIFT_DETECTED\" }"
  log_group_name = aws_cloudwatch_log_group.replay.name

  metric_transformation {
    name          = "DriftEvents"
    namespace     = local.namespace
    value         = "1"
    unit          = "Count"
    default_value = "0"
  }
}

# ── SNS topic for alarms ───────────────────────────────────────────────────────
resource "aws_sns_topic" "alarms" {
  name = "${local.prefix}-alarms"

  tags = {
    Name = "${local.prefix}-alarms"
  }
}

# ── Alarms ────────────────────────────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "auth_failures" {
  alarm_name          = "${local.prefix}-auth-failures-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "AuthFailures"
  namespace           = local.namespace
  period              = 300
  statistic           = "Sum"
  threshold           = var.auth_failure_alarm_threshold
  alarm_description   = "Authentication failure rate exceeded ${var.auth_failure_alarm_threshold} in a 5-minute window."
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${local.prefix}-auth-failures-high"
  }
}

resource "aws_cloudwatch_metric_alarm" "app_errors" {
  alarm_name          = "${local.prefix}-app-errors-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "AppErrors"
  namespace           = local.namespace
  period              = 300
  statistic           = "Sum"
  threshold           = var.app_error_alarm_threshold
  alarm_description   = "Application error rate exceeded ${var.app_error_alarm_threshold} in a 5-minute window."
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${local.prefix}-app-errors-high"
  }
}

# ── CloudWatch dashboard ───────────────────────────────────────────────────────
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.prefix}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 8
        height = 6
        properties = {
          title  = "Authentication Failures"
          period = 300
          stat   = "Sum"
          view   = "timeSeries"
          metrics = [
            [local.namespace, "AuthFailures"]
          ]
          annotations = {
            horizontal = [{ value = var.auth_failure_alarm_threshold, label = "Alarm threshold" }]
          }
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 0
        width  = 8
        height = 6
        properties = {
          title  = "Application Errors"
          period = 300
          stat   = "Sum"
          view   = "timeSeries"
          metrics = [
            [local.namespace, "AppErrors"]
          ]
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 0
        width  = 8
        height = 6
        properties = {
          title  = "Drift Detection Events"
          period = 300
          stat   = "Sum"
          view   = "timeSeries"
          metrics = [
            [local.namespace, "DriftEvents"]
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Golden-Case Accuracy (%)"
          period = 3600
          stat   = "Average"
          view   = "timeSeries"
          metrics = [
            [local.namespace, "GoldenCaseAccuracy"]
          ]
          yAxis = { left = { min = 0, max = 100 } }
        }
      },
      {
        type   = "log"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Recent Application Errors"
          query  = "SOURCE '${aws_cloudwatch_log_group.app.name}' | filter level = 'ERROR' | sort @timestamp desc | limit 20"
          region = "us-east-1"
          view   = "table"
        }
      }
    ]
  })
}
