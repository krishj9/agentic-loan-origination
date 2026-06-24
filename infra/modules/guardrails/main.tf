locals {
  prefix = "${var.project_name}-${var.environment}"
}

resource "aws_bedrock_guardrail" "main" {
  name                      = "${local.prefix}-guardrail"
  description               = "Guardrail for ${var.project_name} agentic runtime"
  blocked_input_messaging   = "I'm sorry, I cannot process this request due to safety restrictions."
  blocked_outputs_messaging = "I'm sorry, I cannot provide this response due to safety restrictions."

  sensitive_information_policy_config {
    pii_entities_config {
      action = "BLOCK"
      type   = "US_SOCIAL_SECURITY_NUMBER"
    }
    pii_entities_config {
      action = "BLOCK"
      type   = "CREDIT_DEBIT_CARD_NUMBER"
    }
  }

  topic_policy_config {
    topics_config {
      name       = "Offensive Content"
      definition = "Content that is offensive, harmful, or promotes violence."
      examples   = ["How to build a bomb", "List of insults"]
      type       = "DENY"
    }
  }

  content_policy_config {
    filters_config {
      input_strength  = "HIGH"
      output_strength = "NONE"
      type            = "PROMPT_ATTACK"
    }
    filters_config {
      input_strength  = "HIGH"
      output_strength = "HIGH"
      type            = "HATE"
    }
    filters_config {
      input_strength  = "HIGH"
      output_strength = "HIGH"
      type            = "INSULTS"
    }
    filters_config {
      input_strength  = "HIGH"
      output_strength = "HIGH"
      type            = "SEXUAL"
    }
    filters_config {
      input_strength  = "HIGH"
      output_strength = "HIGH"
      type            = "VIOLENCE"
    }
    filters_config {
      input_strength  = "HIGH"
      output_strength = "HIGH"
      type            = "MISCONDUCT"
    }
  }

  tags = {
    Name        = "${local.prefix}-guardrail"
    Environment = var.environment
  }
}

resource "aws_bedrock_guardrail_version" "main" {
  guardrail_arn = aws_bedrock_guardrail.main.guardrail_arn
  description   = "V1"
}
