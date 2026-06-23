# Bootstrap — creates the Terraform remote state backend.
#
# Run ONCE before the main demo environment:
#   terraform -chdir=infra/bootstrap init
#   terraform -chdir=infra/bootstrap apply
#
# Uses a local backend deliberately (chicken-egg: cannot store state
# for the state-bucket in that same bucket).
#
# After apply, record the outputs in infra/envs/demo/backend.tf.

terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50, < 6.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = "shared"
      ManagedBy   = "terraform-bootstrap"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  prefix = "${var.project_name}-${var.environment}"
}

# ── KMS key for state-bucket encryption ───────────────────────────────────────
resource "aws_kms_key" "tf_state" {
  description             = "Encryption key for the ${local.prefix} Terraform state bucket."
  deletion_window_in_days = 10
  enable_key_rotation     = true

  policy = data.aws_iam_policy_document.kms_state.json

  tags = {
    Name = "${local.prefix}-tf-state-key"
  }
}

resource "aws_kms_alias" "tf_state" {
  name          = "alias/${local.prefix}-tf-state"
  target_key_id = aws_kms_key.tf_state.key_id
}

data "aws_iam_policy_document" "kms_state" {
  # Allow the owning account to manage the key via IAM policies.
  statement {
    sid    = "EnableIAMUserPermissions"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }

    actions   = ["kms:*"]
    resources = ["*"]
  }
}

# ── S3 state bucket ────────────────────────────────────────────────────────────
resource "aws_s3_bucket" "tf_state" {
  bucket = var.state_bucket_name

  # Guard against accidental deletion of remote state.
  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name = var.state_bucket_name
  }
}

resource "aws_s3_bucket_versioning" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.tf_state.arn
      sse_algorithm     = "aws:kms"
    }

    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "tf_state" {
  bucket = aws_s3_bucket.tf_state.id
  policy = data.aws_iam_policy_document.tf_state_bucket.json

  depends_on = [aws_s3_bucket_public_access_block.tf_state]
}

data "aws_iam_policy_document" "tf_state_bucket" {
  statement {
    sid    = "DenyNonTLS"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:*"]

    resources = [
      aws_s3_bucket.tf_state.arn,
      "${aws_s3_bucket.tf_state.arn}/*",
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

# ── DynamoDB lock table ────────────────────────────────────────────────────────
resource "aws_dynamodb_table" "tf_lock" {
  name         = var.lock_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  server_side_encryption {
    enabled = true
  }

  point_in_time_recovery {
    enabled = false # Not needed for a lock table
  }

  tags = {
    Name = var.lock_table_name
  }
}
