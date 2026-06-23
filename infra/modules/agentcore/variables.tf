variable "project_name" {
  type        = string
  description = "Short project identifier."
}

variable "environment" {
  type        = string
  description = "Deployment environment."
}

variable "region" {
  type        = string
  description = "AWS region in which to provision the AgentCore Runtime and Gateway."
}

variable "runtime_role_arn" {
  type        = string
  description = "IAM role ARN for the AgentCore Runtime execution role."
}

variable "gateway_role_arn" {
  type        = string
  description = "IAM role ARN for the AgentCore Gateway tool execution role."
}

variable "bedrock_model_id" {
  type        = string
  description = "Bedrock foundation model ID to configure as the supervisor LLM."
  default     = "anthropic.claude-3-5-sonnet-20241022-v2:0"
}
