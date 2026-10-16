"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthContext } from "@/lib/AuthContext";
import LandingPage from "@/components/LandingPage";

/**
 * Root route — routes based on authentication status
 *
 * - Unauthenticated users: shows landing page
 * - Authenticated users: redirects to /incidents
 * - Loading: shows spinner while checking authentication status
 */
export default function RootPage() {
  const router = useRouter();
  const { isAuthenticated, authReady } = useAuthContext();

  useEffect(() => {
    // Wait for authentication check to complete
    if (!authReady) return;

    // Redirect authenticated users to incidents dashboard
    if (isAuthenticated) {
      router.replace("/incidents");
    }
  }, [isAuthenticated, authReady, router]);

  // Show loading state while checking authentication
  if (!authReady) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-slate-700 border-t-indigo-600 rounded-full animate-spin" />
          <p className="text-slate-400">Loading...</p>
        </div>
      </div>
    );
  }

  // Show landing page to unauthenticated users
  if (!isAuthenticated) {
    return <LandingPage />;
  }

  // Authenticated users will be redirected by useEffect, show loading spinner while redirect happens
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="flex flex-col items-center gap-4">
        <div className="w-12 h-12 border-4 border-slate-700 border-t-indigo-600 rounded-full animate-spin" />
        <p className="text-slate-400">Redirecting...</p>
      </div>
    </div>
  );
}
