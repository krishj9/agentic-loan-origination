/**
 * Cognito authentication configuration.
 * Environment variables are loaded from .env and validated at runtime.
 */

export interface AuthConfig {
  region: string;
  userPoolId: string;
  userPoolClientId: string;
  oauth: {
    domain: string;
    redirectSignIn: string;
    redirectSignOut: string;
    responseType: 'code'; // PKCE flow
  };
}

/**
 * Load and validate auth configuration from environment variables.
 * Throws if required variables are missing.
 */
export function getAuthConfig(): AuthConfig {
  const region = import.meta.env.VITE_AWS_REGION;
  const userPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID;
  const userPoolClientId = import.meta.env.VITE_COGNITO_USER_POOL_CLIENT_ID;
  const oauthDomain = import.meta.env.VITE_COGNITO_OAUTH_DOMAIN;
  const redirectSignIn = import.meta.env.VITE_COGNITO_REDIRECT_SIGN_IN || window.location.origin;
  const redirectSignOut = import.meta.env.VITE_COGNITO_REDIRECT_SIGN_OUT || window.location.origin;

  if (!region || !userPoolId || !userPoolClientId || !oauthDomain) {
    throw new Error(
      'Missing required auth config. Ensure VITE_AWS_REGION, VITE_COGNITO_USER_POOL_ID, ' +
        'VITE_COGNITO_USER_POOL_CLIENT_ID, and VITE_COGNITO_OAUTH_DOMAIN are set.'
    );
  }

  return {
    region,
    userPoolId,
    userPoolClientId,
    oauth: {
      domain: oauthDomain,
      redirectSignIn,
      redirectSignOut,
      responseType: 'code',
    },
  };
}
