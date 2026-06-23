output "bucket_id" {
  description = "Name (ID) of the documents S3 bucket."
  value       = aws_s3_bucket.documents.id
}

output "bucket_arn" {
  description = "ARN of the documents S3 bucket."
  value       = aws_s3_bucket.documents.arn
}

output "kms_key_id" {
  description = "Key ID of the documents bucket CMK."
  value       = aws_kms_key.documents.key_id
}

output "kms_key_arn" {
  description = "ARN of the documents bucket CMK."
  value       = aws_kms_key.documents.arn
}

output "kms_key_alias_arn" {
  description = "ARN of the KMS key alias."
  value       = aws_kms_alias.documents.arn
}

output "access_logs_bucket_id" {
  description = "Name of the S3 access-logging bucket."
  value       = aws_s3_bucket.access_logs.id
}
