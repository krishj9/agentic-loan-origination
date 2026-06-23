# IAM module — creates the three least-privilege execution roles needed by the
# loan origination system (design §4.3, requirements §4.3).
#
# Roles:
#   runtime-exec  — assumed by AgentCore Runtime to run the LangGraph supervisor.
#                   Permissions: S3 r/w (project bucket), Bedrock model invocation,
#                   CloudWatch Logs, SSM parameter reads for AgentCore outputs.
#
#   backend       — assumed by the FastAPI task (ECS or Lambda).
#                   Permissions: S3 presigned-URL scopes (incoming write, archive
#                   read), CloudWatch Logs + Metrics, AgentCore Runtime invocation.
#
#   gateway-tool  — assumed by AgentCore Gateway when it proxies tool calls.
#                   Permissions: S3 read (incoming + extracted), SSM reads,
#                   CloudWatch Logs.
#
# IAM policies reference exact S3 bucket + KMS key ARNs to enforce least-privilege.

locals {
  prefix = "${var.project_name}-${var.environment}"
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ── Common trust policies ──────────────────────────────────────────────────────

data "aws_iam_policy_document" "bedrock_trust" {
  statement {
    sid    = "BedrockAssumeRole"
    effect = "Allow"

    principals {
      type = "Service"
      identifiers = [
        "bedrock.amazonaws.com",
        "bedrock-agentcore.amazonaws.com",
      ]
    }

    actions = ["sts:AssumeRole"]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

data "aws_iam_policy_document" "compute_trust" {
  statement {
    sid    = "ComputeAssumeRole"
    effect = "Allow"

    principals {
      type = "Service"
      identifiers = [
        "ecs-tasks.amazonaws.com",
        "lambda.amazonaws.com",
      ]
    }

    actions = ["sts:AssumeRole"]
  }
}

# ════════════════════════════════════════════════════════════════════════════════
# Runtime execution role
# ════════════════════════════════════════════════════════════════════════════════

resource "aws_iam_role" "runtime_exec" {
  name               = "${local.prefix}-runtime-exec-role"
  description        = "AgentCore Runtime execution role for the LangGraph supervisor."
  assume_role_policy = data.aws_iam_policy_document.bedrock_trust.json

  tags = {
    Name = "${local.prefix}-runtime-exec-role"
  }
}

# S3: read incoming and extracted; write extracted and archive.
data "aws_iam_policy_document" "runtime_s3" {
  statement {
    sid    = "ReadIncoming"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
    ]

    resources = [
      "${var.bucket_arn}/incoming/*",
    ]
  }

  statement {
    sid    = "ReadWriteExtracted"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]

    resources = [
      "${var.bucket_arn}/extracted/*",
    ]
  }

  statement {
    sid    = "WriteArchive"
    effect = "Allow"

    actions = [
      "s3:PutObject",
      "s3:GetObject",
    ]

    resources = [
      "${var.bucket_arn}/archive/*",
    ]
  }

  statement {
    sid    = "ListBucket"
    effect = "Allow"

    actions = ["s3:ListBucket"]

    resources = [var.bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["incoming/*", "extracted/*", "archive/*"]
    }
  }
}

resource "aws_iam_policy" "runtime_s3" {
  name        = "${local.prefix}-runtime-s3"
  description = "S3 read/write for the AgentCore Runtime role."
  policy      = data.aws_iam_policy_document.runtime_s3.json

  tags = { Name = "${local.prefix}-runtime-s3" }
}

resource "aws_iam_role_policy_attachment" "runtime_s3" {
  role       = aws_iam_role.runtime_exec.name
  policy_arn = aws_iam_policy.runtime_s3.arn
}

# Bedrock: invoke specific models only.
data "aws_iam_policy_document" "runtime_bedrock" {
  statement {
    sid    = "InvokeBedrockModels"
    effect = "Allow"

    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]

    resources = [
      "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/${var.bedrock_model_id}",
    ]
  }

  statement {
    sid    = "ApplyGuardrails"
    effect = "Allow"

    actions = [
      "bedrock:ApplyGuardrail",
    ]

    resources = ["arn:aws:bedrock:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:guardrail/*"]
  }
}

resource "aws_iam_policy" "runtime_bedrock" {
  name        = "${local.prefix}-runtime-bedrock"
  description = "Bedrock model invocation for the AgentCore Runtime role."
  policy      = data.aws_iam_policy_document.runtime_bedrock.json

  tags = { Name = "${local.prefix}-runtime-bedrock" }
}

resource "aws_iam_role_policy_attachment" "runtime_bedrock" {
  role       = aws_iam_role.runtime_exec.name
  policy_arn = aws_iam_policy.runtime_bedrock.arn
}

# CloudWatch Logs: project log groups only.
data "aws_iam_policy_document" "runtime_logs" {
  statement {
    sid    = "PutLogs"
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]

    resources = [
      "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:${var.log_group_prefix}*",
    ]
  }
}

resource "aws_iam_policy" "runtime_logs" {
  name        = "${local.prefix}-runtime-logs"
  description = "CloudWatch Logs write access for the AgentCore Runtime role."
  policy      = data.aws_iam_policy_document.runtime_logs.json

  tags = { Name = "${local.prefix}-runtime-logs" }
}

resource "aws_iam_role_policy_attachment" "runtime_logs" {
  role       = aws_iam_role.runtime_exec.name
  policy_arn = aws_iam_policy.runtime_logs.arn
}

# KMS: encrypt/decrypt project bucket objects.
data "aws_iam_policy_document" "runtime_kms" {
  statement {
    sid    = "UseDocumentsCMK"
    effect = "Allow"

    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey",
      "kms:DescribeKey",
    ]

    resources = [var.kms_key_arn]
  }
}

resource "aws_iam_policy" "runtime_kms" {
  name        = "${local.prefix}-runtime-kms"
  description = "KMS decrypt/encrypt for the documents bucket CMK (runtime role)."
  policy      = data.aws_iam_policy_document.runtime_kms.json

  tags = { Name = "${local.prefix}-runtime-kms" }
}

resource "aws_iam_role_policy_attachment" "runtime_kms" {
  role       = aws_iam_role.runtime_exec.name
  policy_arn = aws_iam_policy.runtime_kms.arn
}

# SSM: read AgentCore provisioning outputs.
data "aws_iam_policy_document" "runtime_ssm" {
  statement {
    sid    = "ReadAgentCoreParams"
    effect = "Allow"

    actions = ["ssm:GetParameter", "ssm:GetParameters"]

    resources = [
      "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/agentcore/*",
    ]
  }
}

resource "aws_iam_policy" "runtime_ssm" {
  name        = "${local.prefix}-runtime-ssm"
  description = "SSM parameter reads for AgentCore provisioning outputs (runtime role)."
  policy      = data.aws_iam_policy_document.runtime_ssm.json

  tags = { Name = "${local.prefix}-runtime-ssm" }
}

resource "aws_iam_role_policy_attachment" "runtime_ssm" {
  role       = aws_iam_role.runtime_exec.name
  policy_arn = aws_iam_policy.runtime_ssm.arn
}

# ════════════════════════════════════════════════════════════════════════════════
# Backend (FastAPI task) role
# ════════════════════════════════════════════════════════════════════════════════

resource "aws_iam_role" "backend" {
  name               = "${local.prefix}-backend-role"
  description        = "Execution role for the FastAPI backend service."
  assume_role_policy = data.aws_iam_policy_document.compute_trust.json

  tags = {
    Name = "${local.prefix}-backend-role"
  }
}

data "aws_iam_policy_document" "backend_s3" {
  statement {
    sid    = "WriteIncoming"
    effect = "Allow"

    # Allow generating presigned PUT URLs for direct SPA-to-S3 uploads.
    actions = ["s3:PutObject"]

    resources = ["${var.bucket_arn}/incoming/*"]
  }

  statement {
    sid    = "ReadArchive"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
    ]

    resources = [
      "${var.bucket_arn}/archive/*",
      "${var.bucket_arn}/extracted/*",
    ]
  }
}

resource "aws_iam_policy" "backend_s3" {
  name        = "${local.prefix}-backend-s3"
  description = "S3 presigned upload + archive read for the backend role."
  policy      = data.aws_iam_policy_document.backend_s3.json

  tags = { Name = "${local.prefix}-backend-s3" }
}

resource "aws_iam_role_policy_attachment" "backend_s3" {
  role       = aws_iam_role.backend.name
  policy_arn = aws_iam_policy.backend_s3.arn
}

data "aws_iam_policy_document" "backend_kms" {
  statement {
    sid    = "UseDocumentsCMK"
    effect = "Allow"

    actions = [
      "kms:GenerateDataKey",
      "kms:Decrypt",
      "kms:DescribeKey",
    ]

    resources = [var.kms_key_arn]
  }
}

resource "aws_iam_policy" "backend_kms" {
  name        = "${local.prefix}-backend-kms"
  description = "KMS access for the documents bucket CMK (backend role)."
  policy      = data.aws_iam_policy_document.backend_kms.json

  tags = { Name = "${local.prefix}-backend-kms" }
}

resource "aws_iam_role_policy_attachment" "backend_kms" {
  role       = aws_iam_role.backend.name
  policy_arn = aws_iam_policy.backend_kms.arn
}

data "aws_iam_policy_document" "backend_logs_metrics" {
  statement {
    sid    = "WriteLogs"
    effect = "Allow"

    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:${var.log_group_prefix}*",
    ]
  }

  statement {
    sid    = "PutMetrics"
    effect = "Allow"

    actions = ["cloudwatch:PutMetricData"]

    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["${var.project_name}/${var.environment}"]
    }
  }
}

resource "aws_iam_policy" "backend_logs_metrics" {
  name        = "${local.prefix}-backend-logs-metrics"
  description = "CloudWatch Logs + Metrics for the backend role."
  policy      = data.aws_iam_policy_document.backend_logs_metrics.json

  tags = { Name = "${local.prefix}-backend-logs-metrics" }
}

resource "aws_iam_role_policy_attachment" "backend_logs_metrics" {
  role       = aws_iam_role.backend.name
  policy_arn = aws_iam_policy.backend_logs_metrics.arn
}

# Allow backend to start AgentCore Runtime sessions.
data "aws_iam_policy_document" "backend_agentcore" {
  statement {
    sid    = "InvokeAgentCoreRuntime"
    effect = "Allow"

    actions = [
      "bedrock-agentcore:InvokeAgentRuntime",
      "bedrock-agentcore:CreateAgentRuntimeSession",
      "bedrock-agentcore:GetAgentRuntime",
    ]

    resources = [
      "arn:aws:bedrock-agentcore:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:agent-runtime/*",
    ]
  }
}

resource "aws_iam_policy" "backend_agentcore" {
  name        = "${local.prefix}-backend-agentcore"
  description = "AgentCore Runtime session invocation for the backend role."
  policy      = data.aws_iam_policy_document.backend_agentcore.json

  tags = { Name = "${local.prefix}-backend-agentcore" }
}

resource "aws_iam_role_policy_attachment" "backend_agentcore" {
  role       = aws_iam_role.backend.name
  policy_arn = aws_iam_policy.backend_agentcore.arn
}

# ════════════════════════════════════════════════════════════════════════════════
# Gateway tool execution role
# ════════════════════════════════════════════════════════════════════════════════

resource "aws_iam_role" "gateway_tool" {
  name               = "${local.prefix}-gateway-tool-role"
  description        = "AgentCore Gateway role for executing tool backends."
  assume_role_policy = data.aws_iam_policy_document.bedrock_trust.json

  tags = {
    Name = "${local.prefix}-gateway-tool-role"
  }
}

data "aws_iam_policy_document" "gateway_tool" {
  statement {
    sid    = "ReadDocuments"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
    ]

    resources = [
      "${var.bucket_arn}/incoming/*",
      "${var.bucket_arn}/extracted/*",
    ]
  }

  statement {
    sid    = "UseDocumentsCMK"
    effect = "Allow"

    actions = [
      "kms:Decrypt",
      "kms:DescribeKey",
    ]

    resources = [var.kms_key_arn]
  }

  statement {
    sid    = "WriteLogs"
    effect = "Allow"

    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = [
      "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:${var.log_group_prefix}*",
    ]
  }

  statement {
    sid    = "ReadSSMParams"
    effect = "Allow"

    actions = ["ssm:GetParameter"]

    resources = [
      "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter/${var.project_name}/${var.environment}/*",
    ]
  }
}

resource "aws_iam_policy" "gateway_tool" {
  name        = "${local.prefix}-gateway-tool"
  description = "Least-privilege policy for the AgentCore Gateway tool execution role."
  policy      = data.aws_iam_policy_document.gateway_tool.json

  tags = { Name = "${local.prefix}-gateway-tool" }
}

resource "aws_iam_role_policy_attachment" "gateway_tool" {
  role       = aws_iam_role.gateway_tool.name
  policy_arn = aws_iam_policy.gateway_tool.arn
}
