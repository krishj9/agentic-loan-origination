output "user_pool_id" {
  description = "Cognito user pool ID."
  value       = aws_cognito_user_pool.main.id
}

output "user_pool_arn" {
  description = "ARN of the Cognito user pool."
  value       = aws_cognito_user_pool.main.arn
}

output "spa_client_id" {
  description = "App client ID for the React SPA (no secret, PKCE)."
  value       = aws_cognito_user_pool_client.spa.id
}

output "hosted_ui_domain" {
  description = "Cognito hosted UI domain prefix."
  value       = aws_cognito_user_pool_domain.main.domain
}

output "hosted_ui_base_url" {
  description = "Full Cognito hosted UI base URL."
  value       = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${aws_cognito_user_pool_domain.main.cloudfront_distribution}.amazoncognito.com"
}

output "oidc_discovery_url" {
  description = "OIDC discovery URL for the user pool (used by the backend JWT validator)."
  value       = "https://cognito-idp.${aws_cognito_user_pool.main.id}.amazonaws.com/${aws_cognito_user_pool.main.id}"
}

output "loan_officer_group_name" {
  description = "Cognito group name for loan officers."
  value       = aws_cognito_user_group.loan_officer.name
}

output "operator_group_name" {
  description = "Cognito group name for operators."
  value       = aws_cognito_user_group.operator.name
}
