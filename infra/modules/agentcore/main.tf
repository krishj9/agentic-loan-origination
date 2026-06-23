# AgentCore module — provisions Amazon Bedrock AgentCore Runtime and Gateway.
#
# AgentCore Runtime and Gateway are managed-plane resources that as of Terraform
# AWS provider v5.x do not have first-class resource support.  This module
# therefore falls back to the approved plan workaround:
#
#   data "external" → scripts/agentcore_provision.py (boto3, idempotent)
#
# The Python script reads a JSON query from stdin, creates/updates the Runtime
# and Gateway (or skips gracefully if the service is unavailable in the region),
# and writes JSON results to stdout.  Terraform then exposes those values as
# module outputs.
#
# Re-provisioning is triggered only when the trigger inputs change (role ARN,
# project name, or environment), keeping plans fast.

locals {
  prefix      = "${var.project_name}-${var.environment}"
  script_path = "${abspath(path.module)}/../../../scripts/agentcore_provision.py"
}

# ── AgentCore provisioning via boto3 ──────────────────────────────────────────
data "external" "agentcore" {
  program = ["python3", local.script_path]

  query = {
    project_name     = var.project_name
    environment      = var.environment
    region           = var.region
    runtime_role_arn = var.runtime_role_arn
    gateway_role_arn = var.gateway_role_arn
    bedrock_model_id = var.bedrock_model_id
  }
}
