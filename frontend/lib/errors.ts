/**
 * DataGhost – shared error classification utilities.
 *
 * isBackendWakeUpError: returns true when the error is a Render free-tier
 * cold-start (network timeout / 502 from the Vercel proxy).  These should
 * show a friendly "Backend is waking up" banner rather than a red error.
 */

import { ApiConnectionError } from "@/lib/auth";

export function isBackendWakeUpError(err: unknown): boolean {
  if (err instanceof ApiConnectionError) return true;
  if (err instanceof Error) {
    const m = err.message.toLowerCase();
    return (
      m.includes("failed to fetch") ||
      m.includes("backend is waking up") ||
      m.includes("networkerror") ||
      m.includes("network request failed") ||
      m.includes("502") ||
      m.includes("503") ||
      m.includes("unavailable") ||
      m.includes("backend unavailable")
    );
  }
  return false;
}
