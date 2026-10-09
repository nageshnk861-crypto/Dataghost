"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthContext } from "@/lib/AuthContext";

/**
 * Redirects to /login if not authenticated (works for BOTH jwt and firebase auth methods).
 * Returns true once auth is confirmed so pages can gate rendering.
 *
 * Uses AuthContext instead of raw JWT check so Firebase-authenticated users
 * are not incorrectly redirected.
 */
export function useAuthGuard(): boolean {
  const router = useRouter();
  const { authReady, isAuthenticated } = useAuthContext();

  useEffect(() => {
    if (authReady && !isAuthenticated) {
      router.replace("/login");
    }
  }, [authReady, isAuthenticated, router]);

  // Ready once auth is resolved AND user is authenticated.
  return authReady && isAuthenticated;
}
