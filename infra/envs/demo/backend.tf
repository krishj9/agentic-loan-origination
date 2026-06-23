# Remote state backend.
#
# Run `infra/bootstrap` first to create the state bucket and lock table, then
# fill in the values below and run `terraform init` in this directory.
#
# The CI pipeline uses `terraform init -backend=false` for validate/lint jobs.

terraform {
  backend "s3" {
    bucket         = "loan-origination-tf-state-demo"
    key            = "demo/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "loan-origination-tf-lock"
    encrypt        = true
  }
}
