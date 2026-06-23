output "state_bucket_name" {
  description = "Name of the S3 bucket that stores Terraform state."
  value       = aws_s3_bucket.tf_state.id
}

output "state_bucket_arn" {
  description = "ARN of the S3 state bucket."
  value       = aws_s3_bucket.tf_state.arn
}

output "state_kms_key_arn" {
  description = "ARN of the KMS key used to encrypt the state bucket."
  value       = aws_kms_key.tf_state.arn
}

output "lock_table_name" {
  description = "Name of the DynamoDB table used for state locking."
  value       = aws_dynamodb_table.tf_lock.id
}

output "backend_hcl_snippet" {
  description = "Paste this into infra/envs/demo/backend.tf to activate the S3 backend."
  value       = <<-EOT
    terraform {
      backend "s3" {
        bucket         = "${aws_s3_bucket.tf_state.id}"
        key            = "demo/terraform.tfstate"
        region         = "${var.region}"
        dynamodb_table = "${aws_dynamodb_table.tf_lock.id}"
        encrypt        = true
        kms_key_id     = "${aws_kms_key.tf_state.arn}"
      }
    }
  EOT
}
