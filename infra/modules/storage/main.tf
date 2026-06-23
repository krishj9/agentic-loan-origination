# Storage module — S3 bucket for document storage with KMS encryption,
# lifecycle policies, access logging, and non-TLS deny bucket policy.
#
# S3 prefix layout (design §9.2):
#   incoming/{application_id}/   — raw PDF uploads (presigned PUT from backend)
#   extracted/{application_id}/  — normalized canonical JSON from LlamaParse
#   archive/{application_id}/    — final decision JSON + PDF (audit artifacts)
#
# Access logging is written to a dedicated logging bucket in the same account.

locals {
  prefix = "${var.project_name}-${var.environment}"
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ── KMS customer-managed key ───────────────────────────────────────────────────
resource "aws_kms_key" "documents" {
  description             = "CMK for the ${local.prefix} document S3 bucket."
  deletion_window_in_days = 14
  enable_key_rotation     = true

  policy = data.aws_iam_policy_document.kms_key_policy.json

  tags = {
    Name = "${local.prefix}-documents-key"
  }
}

resource "aws_kms_alias" "documents" {
  name          = "alias/${local.prefix}-documents"
  target_key_id = aws_kms_key.documents.key_id
}

# Grant the account root full control so IAM policies can delegate further.
data "aws_iam_policy_document" "kms_key_policy" {
  statement {
    sid    = "EnableIAMRootAccess"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }

    actions   = ["kms:*"]
    resources = ["*"]
  }
}

# ── Access logging bucket ─────────────────────────────────────────────────────
resource "aws_s3_bucket" "access_logs" {
  bucket = "${local.prefix}-s3-access-logs"

  tags = {
    Name = "${local.prefix}-s3-access-logs"
  }
}

resource "aws_s3_bucket_public_access_block" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    id     = "expire-access-logs"
    status = "Enabled"

    filter {}

    expiration {
      days = var.access_log_retention_days
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ── Main documents bucket ──────────────────────────────────────────────────────
resource "aws_s3_bucket" "documents" {
  bucket = "${local.prefix}-documents"

  tags = {
    Name = "${local.prefix}-documents"
  }
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket = aws_s3_bucket.documents.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id

  versioning_configuration {
    # Versioning enables point-in-time recovery for archive artifacts.
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.documents.arn
      sse_algorithm     = "aws:kms"
    }

    # Bucket-key reduces KMS API calls for high-throughput workloads.
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_logging" "documents" {
  bucket        = aws_s3_bucket.documents.id
  target_bucket = aws_s3_bucket.access_logs.id
  target_prefix = "documents/"
}

# ── Lifecycle configuration ────────────────────────────────────────────────────
resource "aws_s3_bucket_lifecycle_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  rule {
    id     = "expire-incoming"
    status = "Enabled"

    filter {
      prefix = "incoming/"
    }

    # Raw uploads can be removed after extraction is confirmed.
    expiration {
      days = var.incoming_retention_days
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }

  rule {
    id     = "expire-extracted"
    status = "Enabled"

    filter {
      prefix = "extracted/"
    }

    expiration {
      days = var.extracted_retention_days
    }

    noncurrent_version_expiration {
      noncurrent_days = 14
    }
  }

  rule {
    id     = "transition-archive-to-ia"
    status = "Enabled"

    filter {
      prefix = "archive/"
    }

    # Move archive artifacts to cheaper storage after 90 days.
    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
  }
}

# ── Bucket policy: deny all non-TLS requests ──────────────────────────────────
resource "aws_s3_bucket_policy" "documents" {
  bucket = aws_s3_bucket.documents.id
  policy = data.aws_iam_policy_document.documents_bucket.json

  depends_on = [aws_s3_bucket_public_access_block.documents]
}

data "aws_iam_policy_document" "documents_bucket" {
  statement {
    sid    = "DenyNonTLS"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:*"]

    resources = [
      aws_s3_bucket.documents.arn,
      "${aws_s3_bucket.documents.arn}/*",
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  statement {
    sid    = "DenyUnencryptedUploads"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:PutObject"]

    resources = ["${aws_s3_bucket.documents.arn}/*"]

    condition {
      test     = "StringNotEquals"
      variable = "s3:x-amz-server-side-encryption"
      values   = ["aws:kms"]
    }
  }
}

# ── CORS for presigned URL uploads from the React SPA ─────────────────────────
resource "aws_s3_bucket_cors_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT"]
    allowed_origins = var.cors_allowed_origins
    expose_headers  = ["ETag"]
    max_age_seconds = 3600
  }
}
