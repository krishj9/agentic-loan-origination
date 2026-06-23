/**
 * Authentication context using AWS Amplify with Cognito.
 * Implements PKCE flow with Hosted UI redirect and secure token storage.
 */

import { Amplify } from 'aws-amplify';
import {
  signOut,
  getCurrentUser,
  fetchAuthSession,
  fetchUserAttributes,
} from 'aws-amplify/auth';
import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { getAuthConfig } from '../config/auth';

interface AuthUser {
  userId: string;
  username: string;
  email?: string;
  groups: string[];
}

interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  getAccessToken: () => Promise<string | null>;
  hasRole: (role: string) => boolean;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// Configure Amplify once at module load
const authConfig = getAuthConfig();
Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: authConfig.userPoolId,
      userPoolClientId: authConfig.userPoolClientId,
      loginWith: {
        oauth: {
          domain: authConfig.oauth.domain,
          scopes: ['openid', 'email', 'profile'],
          redirectSignIn: [authConfig.oauth.redirectSignIn],
          redirectSignOut: [authConfig.oauth.redirectSignOut],
          responseType: authConfig.oauth.responseType,
        },
      },
    },
  },
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  /**
   * Extract Cognito groups from user attributes.
   * Groups are stored in 'cognito:groups' claim.
   */
  const extractGroups = useCallback(async (): Promise<string[]> => {
    try {
      const session = await fetchAuthSession();
      const tokens = session.tokens;
      if (!tokens?.idToken?.payload) {
        return [];
      }
      const groups = tokens.idToken.payload['cognito:groups'];
      if (Array.isArray(groups)) {
        return groups.filter((g): g is string => typeof g === 'string');
      }
      return [];
    } catch (error) {
      console.error('[AuthContext] Failed to extract groups:', error);
      return [];
    }
  }, []);

  /**
   * Load current authenticated user on mount and after login.
   */
  const loadUser = useCallback(async () => {
    try {
      setIsLoading(true);
      const currentUser = await getCurrentUser();
      const attributes = await fetchUserAttributes();
      const groups = await extractGroups();

      setUser({
        userId: currentUser.userId,
        username: currentUser.username,
        email: attributes.email,
        groups,
      });
    } catch (error) {
      // User not authenticated
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, [extractGroups]);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  /**
   * Redirect to Cognito Hosted UI for login.
   */
  const login = useCallback(async () => {
    try {
      // Use window.location to redirect to Cognito Hosted UI
      const config = getAuthConfig();
      const redirectUri = encodeURIComponent(config.oauth.redirectSignIn);
      const hostedUIUrl = `https://${config.oauth.domain}/oauth2/authorize?client_id=${config.userPoolClientId}&response_type=code&scope=openid+email+profile&redirect_uri=${redirectUri}`;
      window.location.href = hostedUIUrl;
    } catch (error) {
      console.error('[AuthContext] Login failed:', error);
      throw error;
    }
  }, []);

  /**
   * Sign out and clear tokens.
   */
  const logout = useCallback(async () => {
    try {
      await signOut();
      setUser(null);
    } catch (error) {
      console.error('[AuthContext] Logout failed:', error);
      throw error;
    }
  }, []);

  /**
   * Retrieve access token for API calls.
   * Amplify handles automatic refresh.
   */
  const getAccessToken = useCallback(async (): Promise<string | null> => {
    try {
      const session = await fetchAuthSession();
      return session.tokens?.accessToken?.toString() ?? null;
    } catch (error) {
      console.error('[AuthContext] Failed to get access token:', error);
      return null;
    }
  }, []);

  /**
   * Check if user has a specific role (Cognito group).
   */
  const hasRole = useCallback(
    (role: string): boolean => {
      return user?.groups.includes(role) ?? false;
    },
    [user]
  );

  const value: AuthContextValue = {
    user,
    isLoading,
    isAuthenticated: !!user,
    login,
    logout,
    getAccessToken,
    hasRole,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * Hook to access auth context.
 * Must be used within AuthProvider.
 */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
