# Auth module — Cognito user pool, SPA app client (PKCE), hosted UI domain,
# and the two project role groups (LoanOfficer, Operator).
#
# Cognito issues JWTs compatible with OIDC-based flows (design §4.1).
# The SPA app client uses the Authorization Code + PKCE flow with no client
# secret (design §4.2 / requirements §4.1).

locals {
  prefix = "${var.project_name}-${var.environment}"
}

# ── User pool ──────────────────────────────────────────────────────────────────
resource "aws_cognito_user_pool" "main" {
  name = "${local.prefix}-user-pool"

  # Email is the username identifier.
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 7
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # Email schema attribute.
  schema {
    attribute_data_type      = "String"
    name                     = "email"
    required                 = true
    mutable                  = true
    developer_only_attribute = false

    string_attribute_constraints {
      min_length = 3
      max_length = 254
    }
  }

  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
  }

  # Advanced security tracks anomalous sign-in patterns (AUDIT = log only).
  user_pool_add_ons {
    advanced_security_mode = "AUDIT"
  }

  mfa_configuration = var.mfa_configuration

  # TOTP (software token) MFA is required when mfa_configuration is OPTIONAL or ON.
  # Without at least one MFA method configured, Cognito rejects the request.
  dynamic "software_token_mfa_configuration" {
    for_each = var.mfa_configuration != "OFF" ? [1] : []
    content {
      enabled = true
    }
  }

  # Emit CloudWatch metrics for authentication events.
  # (auth failure logs are written by the application layer to the auth log group)

  tags = {
    Name = "${local.prefix}-user-pool"
  }
}

# ── SPA app client (no client secret, PKCE flow) ──────────────────────────────
resource "aws_cognito_user_pool_client" "spa" {
  name         = "${local.prefix}-spa-client"
  user_pool_id = aws_cognito_user_pool.main.id

  # SPA clients must NOT have a client secret.
  generate_secret = false

  # PKCE Authorization Code flow.
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["email", "openid", "profile"]
  supported_identity_providers         = ["COGNITO"]

  callback_urls = var.callback_urls
  logout_urls   = var.logout_urls

  # Token validity — short-lived access tokens; longer refresh.
  access_token_validity  = 1
  id_token_validity      = 1
  refresh_token_validity = 30

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  # Auth flows allowed for the SPA.
  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  # Prevent user-existence inference attacks.
  prevent_user_existence_errors = "ENABLED"

  read_attributes  = ["email", "email_verified", "name", "given_name", "family_name", "sub"]
  write_attributes = ["email", "name", "given_name", "family_name"]
}

# ── Hosted UI domain ───────────────────────────────────────────────────────────
# Domain prefix must be globally unique across all AWS Cognito user pools.
resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${local.prefix}-auth"
  user_pool_id = aws_cognito_user_pool.main.id
}

# ── Groups (role separation — design §4.3) ─────────────────────────────────────
resource "aws_cognito_user_group" "loan_officer" {
  name         = "LoanOfficer"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Loan officers and reviewers: submit applications and review decisions."
  precedence   = 10
}

resource "aws_cognito_user_group" "operator" {
  name         = "Operator"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Operators and admins: configure rules, inspect logs, manage infrastructure."
  precedence   = 1
}
