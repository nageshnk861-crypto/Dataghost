"use client";
/**
 * DataGhost â€“ low-level auth helpers.
 *
 * ONLY handles localStorage read/write for the DataGhost JWT.
 * No window.location, no React state, no Firebase here.
 *
 * apiFetch is a thin fetch wrapper that:
 *   1. Gets a token from the registered getter (set by AuthProvider).
 *   2. Attaches it as Authorization: Bearer.
 *   3. On 401 â†’ throws AuthError.  NEVER calls window.location or clearToken.
 *      The caller decides what to do.
 *
 * SECURITY: tokens are never logged.
 */

export function getApiBaseUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL?.trim();

  // In browser environment:
  if (typeof window !== "undefined") {
    if (envUrl) {
      const currentHost = window.location.hostname;
      const isDevTunnel = envUrl.includes("devtunnels.ms") || envUrl.includes("localhost") || envUrl.includes("127.0.0.1");
      const isDeployedHost = currentHost.endsWith(".vercel.app") || currentHost.endsWith(".render.com") || (!currentHost.includes("localhost") && !currentHost.includes("127.0.0.1"));

      // If running on deployed domain (e.g. *.vercel.app), ignore devtunnel/localhost URLs
      // and use relative paths ("") so Vercel rewrites route /api/* to the serverless backend.
      if (isDevTunnel && isDeployedHost) {
        return "";
      }
      return envUrl.replace(/\/+$/, "");
    }
    return "";
  }

  // Server-side / SSR default
  if (envUrl && !envUrl.includes("devtunnels.ms")) {
    return envUrl.replace(/\/+$/, "");
  }

  return (
    process.env.BACKEND_INTERNAL_URL ||
    process.env.BACKEND_URL ||
    "http://127.0.0.1:8000"
  ).replace(/\/+$/, "");
}

export const API_BASE = getApiBaseUrl();

// â”€â”€ JWT localStorage â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

const JWT_KEY  = "dg_token";
const USER_KEY = "dg_user";

export function getJwt(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(JWT_KEY);
}
export function saveJwt(token: string) {
  if (typeof window !== "undefined") localStorage.setItem(JWT_KEY, token);
}
export function removeJwt() {
  if (typeof window !== "undefined") {
    localStorage.removeItem(JWT_KEY);
    localStorage.removeItem(USER_KEY);
    sessionStorage.removeItem(JWT_KEY);
    sessionStorage.removeItem(USER_KEY);
  }
}
export function saveUser(u: { username: string; role: string }) {
  if (typeof window !== "undefined")
    localStorage.setItem(USER_KEY, JSON.stringify(u));
}
export function getSavedUser(): { username: string; role: string } | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

// â”€â”€ Legacy aliases (keep old callers working) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export const getToken  = getJwt;
export const setToken  = saveJwt;
export const clearToken = removeJwt;
export const getUser   = getSavedUser;

// â”€â”€ Token getter (set by AuthProvider, never null for long) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// This is a single stable reference â€” we never set it to null between updates.
let _tokenGetter: (() => Promise<string | null>) | null = null;

export function setTokenGetter(fn: () => Promise<string | null>) {
  _tokenGetter = fn;
}

// â”€â”€ AuthError & Diagnostic Errors â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export class AuthError extends Error {
  readonly status = 401;
  constructor(path: string) {
    super(`401 Unauthorized: ${path}`);
    this.name = "AuthError";
  }
}

export class ApiConnectionError extends Error {
  readonly status?: number;
  readonly endpoint: string;
  readonly apiUrl: string;
  readonly originalError: string;

  constructor(endpoint: string, apiUrl: string, message: string, status?: number) {
    const isDev = process.env.NODE_ENV !== "production";
    const devInfo = isDev
      ? ` [Target: ${apiUrl || "(relative proxy)"}${endpoint}${status ? ` | HTTP ${status}` : ""}]`
      : "";
    super(`${message}${devInfo}`);
    this.name = "ApiConnectionError";
    this.status = status;
    this.endpoint = endpoint;
    this.apiUrl = apiUrl;
    this.originalError = message;
  }
}

// â”€â”€ apiFetch â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export async function apiFetch(
  path: string,
  opts?: RequestInit
): Promise<Response> {
  // Get token from AuthProvider getter, or fall back to localStorage directly.
  let token: string | null = null;
  if (_tokenGetter) {
    token = await _tokenGetter();
  } else {
    token = getJwt();
  }

  const isForm = opts?.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(isForm ? {} : { "Content-Type": "application/json" }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    // Bypass Dev Tunnel / proxy interstitials for automated and mobile requests
    "X-Tunnel-Skip-Anti-Phishing-Page": "true",
    "bypass-tunnel-reminder": "true",
    ...((opts?.headers as Record<string, string> | undefined) ?? {}),
  };

  const apiBase = getApiBaseUrl();
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const targetUrl = apiBase ? `${apiBase}${normalizedPath}` : normalizedPath;

  let res: Response;
  try {
    res = await fetch(targetUrl, { ...opts, headers });
  } catch (err: unknown) {
    const originalMsg = err instanceof Error ? err.message : String(err);
    const isNetworkErr =
      originalMsg.includes("fetch") ||
      originalMsg.includes("NetworkError") ||
      originalMsg.includes("Failed to fetch") ||
      originalMsg.includes("Network request failed") ||
      (err instanceof TypeError);

    if (isNetworkErr) {
      const displayUrl = apiBase || (typeof window !== "undefined" ? window.location.origin : "server proxy");
      throw new ApiConnectionError(
        path,
        displayUrl,
        `Backend unavailable. Check that the backend server or Dev Tunnel is running at ${displayUrl}. (${originalMsg})`
      );
    }
    throw err;
  }

  if (res.status === 401) {
    // Do NOT clear the token here â€” the token might still be valid
    // for other requests; this particular endpoint might have a bug.
    // The caller (dashboard, etc.) decides whether to log out.
    // Do NOT call window.location â€” that causes the redirect loop.
    throw new AuthError(path);
  }

  return res;
}

// ── Fetch User Profile from Backend ──────────────────────────────────────────
/**
 * Fetch the authenticated user's profile from the backend GET /auth/me endpoint.
 * This returns the user's role directly from the database, not hardcoded values.
 * 
 * @param token - JWT token to authenticate the request
 * @returns User profile with username and role from the backend, or null on error
 */
export async function fetchUserProfileFromBackend(
  token: string
): Promise<{ username: string; role: string } | null> {
  if (!token) return null;

  const apiBase = getApiBaseUrl();
  const targetUrl = apiBase ? `${apiBase}/auth/me` : `/auth/me`;

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 3000);

    const res = await fetch(targetUrl, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Tunnel-Skip-Anti-Phishing-Page": "true",
        "bypass-tunnel-reminder": "true",
        "Content-Type": "application/json",
      },
      signal: controller.signal,
    });

    clearTimeout(timer);

    if (!res.ok) {
      return null;
    }

    const data = await res.json();
    return {
      username: data.username || "User",
      role: data.role || "analyst",
    };
  } catch (err: unknown) {
    // Silently fail - no fallback to hardcoded admin role
    return null;
  }
}

// â”€â”€ Legacy exports (kept for compatibility) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export function registerTokenGetter(fn: () => Promise<string | null>) {
  setTokenGetter(fn);
}
export function unregisterTokenGetter() {
  // Intentionally a no-op â€” we never null out the getter to avoid null windows.
}
export function registerAuthFailureHandler(_fn: () => void) {
  // No-op â€” auth failures are now handled by callers, not a global callback.
}
export function unregisterAuthFailureHandler() {
  // No-op.
}
export function useAuth() {
  return {
    user: getSavedUser(),
    logout: () => {
      removeJwt();
      if (typeof window !== "undefined") {
        window.location.replace("/login");
      }
    },
  };
}

