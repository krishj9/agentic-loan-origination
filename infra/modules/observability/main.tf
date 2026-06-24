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

# ── Metric filter: golden-case accuracy (P6-T10) ──────────────────────────────
# The evaluation harness emits a structured log line with event_type = METRICS_REPORT
# and accuracy_pct field after each batch run. This filter captures it.
resource "aws_cloudwatch_log_metric_filter" "golden_case_accuracy" {
  name           = "${local.prefix}-golden-case-accuracy"
  pattern        = "{ $.event_type = \"METRICS_REPORT\" }"
  log_group_name = aws_cloudwatch_log_group.replay.name

  metric_transformation {
    name          = "GoldenCaseAccuracy"
    namespace     = local.namespace
    value         = "$.accuracy_pct"
    unit          = "Percent"
    default_value = "100"
  }
}

# ── Metric filter: false-positive count (P6-T10) ──────────────────────────────
resource "aws_cloudwatch_log_metric_filter" "false_positives" {
  name           = "${local.prefix}-false-positives"
  pattern        = "{ $.event_type = \"METRICS_REPORT\" }"
  log_group_name = aws_cloudwatch_log_group.replay.name

  metric_transformation {
    name          = "FalsePositives"
    namespace     = local.namespace
    value         = "$.false_positive_count"
    unit          = "Count"
    default_value = "0"
  }
}

# ── Metric filter: false-negative count (P6-T10) ──────────────────────────────
resource "aws_cloudwatch_log_metric_filter" "false_negatives" {
  name           = "${local.prefix}-false-negatives"
  pattern        = "{ $.event_type = \"METRICS_REPORT\" }"
  log_group_name = aws_cloudwatch_log_group.replay.name

  metric_transformation {
    name          = "FalseNegatives"
    namespace     = local.namespace
    value         = "$.false_negative_count"
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

# ── Alarm: drift events spike (P6-T10) ────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "drift_spike" {
  alarm_name          = "${local.prefix}-drift-spike"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "DriftEvents"
  namespace           = local.namespace
  period              = 3600
  statistic           = "Sum"
  threshold           = var.drift_alarm_threshold
  alarm_description   = "Risk engine drift events exceeded ${var.drift_alarm_threshold} in a 1-hour window. Investigate risk_policy.yaml alignment."
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${local.prefix}-drift-spike"
  }
}

# ── Alarm: golden-case accuracy drop (P6-T10) ─────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "accuracy_drop" {
  alarm_name          = "${local.prefix}-accuracy-drop"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "GoldenCaseAccuracy"
  namespace           = local.namespace
  period              = 3600
  statistic           = "Average"
  threshold           = var.accuracy_alarm_threshold_pct
  alarm_description   = "Golden-case accuracy dropped below ${var.accuracy_alarm_threshold_pct}% in the last hour. Check evaluation harness results."
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]

  tags = {
    Name = "${local.prefix}-accuracy-drop"
  }
}

# ── CloudWatch dashboard (P6-T10 finalized) ───────────────────────────────────
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.prefix}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      # Row 1: Auth + App + Drift (operational health)
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 8
        height = 6
        properties = {
          title  = "Authentication Failures"
          region = var.region
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
          region = var.region
          period = 300
          stat   = "Sum"
          view   = "timeSeries"
          metrics = [
            [local.namespace, "AppErrors"]
          ]
          annotations = {
            horizontal = [{ value = var.app_error_alarm_threshold, label = "Alarm threshold" }]
          }
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
          region = var.region
          period = 3600
          stat   = "Sum"
          view   = "timeSeries"
          metrics = [
            [local.namespace, "DriftEvents"]
          ]
          annotations = {
            horizontal = [{ value = var.drift_alarm_threshold, label = "Drift alarm threshold" }]
          }
        }
      },
      # Row 2: Accuracy + FP/FN (evaluation quality)
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 8
        height = 6
        properties = {
          title  = "Golden-Case Accuracy (%)"
          region = var.region
          period = 3600
          stat   = "Average"
          view   = "timeSeries"
          metrics = [
            [local.namespace, "GoldenCaseAccuracy"]
          ]
          yAxis = { left = { min = 0, max = 100 } }
          annotations = {
            horizontal = [{ value = var.accuracy_alarm_threshold_pct, label = "Min acceptable accuracy" }]
          }
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 6
        width  = 8
        height = 6
        properties = {
          title  = "False Positives & False Negatives"
          region = var.region
          period = 3600
          stat   = "Sum"
          view   = "timeSeries"
          metrics = [
            [local.namespace, "FalsePositives", { label = "False Positives", color = "#ff7f0e" }],
            [local.namespace, "FalseNegatives", { label = "False Negatives", color = "#d62728" }]
          ]
          yAxis = { left = { min = 0 } }
        }
      },
      # Row 2 right: Recent errors log widget
      {
        type   = "log"
        x      = 16
        y      = 6
        width  = 8
        height = 6
        properties = {
          title  = "Recent Application Errors"
          query  = "SOURCE '${aws_cloudwatch_log_group.app.name}' | filter level = 'ERROR' | sort @timestamp desc | limit 20"
          region = var.region
          view   = "table"
        }
      },
      # Row 3: Alarm status widgets
      {
        type   = "alarm"
        x      = 0
        y      = 12
        width  = 8
        height = 3
        properties = {
          title  = "Drift Alarm"
          alarms = [aws_cloudwatch_metric_alarm.drift_spike.arn]
        }
      },
      {
        type   = "alarm"
        x      = 8
        y      = 12
        width  = 8
        height = 3
        properties = {
          title  = "Accuracy Alarm"
          alarms = [aws_cloudwatch_metric_alarm.accuracy_drop.arn]
        }
      },
      {
        type   = "alarm"
        x      = 16
        y      = 12
        width  = 8
        height = 3
        properties = {
          title  = "Auth Failures Alarm"
          alarms = [aws_cloudwatch_metric_alarm.auth_failures.arn]
        }
      }
    ]
  })
}
