"use client";

import { useAuthContext } from "@/lib/AuthContext";
import type { AuthUser, AuthMethod } from "@/lib/AuthContext";

/**
 * Custom hook wrapping AuthContext to provide clean, consistent access
 * to authentication state, user identity, role, and auth actions.
 */
export function useAuth() {
  const {
    user,
    role: legacyRole,
    isAuthenticated,
    isLoading,
    authReady,
    authMethod,
    logout,
    getAuthToken,
    setJwtAuth,
    signalAuthFailure,
  } = useAuthContext() as any;

  return {
    user: user as AuthUser | null,
    role: (user?.role || legacyRole || null) as string | null,
    isAuthenticated: Boolean(isAuthenticated),
    isLoading: Boolean(isLoading ?? !authReady),
    authReady: Boolean(authReady),
    authMethod: (authMethod ?? null) as AuthMethod,
    logout,
    getAuthToken,
    setJwtAuth,
    signalAuthFailure,
  };
}

export type { AuthUser, AuthMethod };
export default useAuth;
