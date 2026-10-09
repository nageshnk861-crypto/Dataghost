"use client";
/**
 * DataGhost – low-level auth helpers.
 *
 * ONLY handles localStorage read/write for the DataGhost JWT.
 * No window.location, no React state, no Firebase here.
 *
 * apiFetch is a thin fetch wrapper that:
 *   1. Gets a token from the registered getter (set by AuthProvider).
 *   2. Attaches it as Authorization: Bearer.
 *   3. On 401 → throws AuthError.  NEVER calls window.location or clearToken.
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

// ── JWT localStorage ──────────────────────────────────────────────────────────

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

// ── Legacy aliases (keep old callers working) ─────────────────────────────────
export const getToken  = getJwt;
export const setToken  = saveJwt;
export const clearToken = removeJwt;
export const getUser   = getSavedUser;

// ── Token getter (set by AuthProvider, never null for long) ───────────────────
// This is a single stable reference — we never set it to null between updates.
let _tokenGetter: (() => Promise<string | null>) | null = null;

export function setTokenGetter(fn: () => Promise<string | null>) {
  _tokenGetter = fn;
}

// ── AuthError & Diagnostic Errors ─────────────────────────────────────────────
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

// ── apiFetch ──────────────────────────────────────────────────────────────────
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
    // Do NOT clear the token here — the token might still be valid
    // for other requests; this particular endpoint might have a bug.
    // The caller (dashboard, etc.) decides whether to log out.
    // Do NOT call window.location — that causes the redirect loop.
    throw new AuthError(path);
  }

  return res;
}

// ── Legacy exports (kept for compatibility) ───────────────────────────────────
export function registerTokenGetter(fn: () => Promise<string | null>) {
  setTokenGetter(fn);
}
export function unregisterTokenGetter() {
  // Intentionally a no-op — we never null out the getter to avoid null windows.
}
export function registerAuthFailureHandler(_fn: () => void) {
  // No-op — auth failures are now handled by callers, not a global callback.
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
