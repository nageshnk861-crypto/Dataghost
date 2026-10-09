"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuthContext } from "../../lib/AuthContext";
import Sidebar from "../../components/Sidebar";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { authReady, isAuthenticated } = useAuthContext();
  const redirectedRef = useRef(false);

  useEffect(() => {
    // Only redirect once — prevent the layout from calling router.replace
    // repeatedly if isAuthenticated flickers (e.g. during Firebase init).
    if (authReady && !isAuthenticated && !redirectedRef.current) {
      redirectedRef.current = true;
      router.replace("/login");
    }
    // Reset redirect flag if user becomes authenticated again (e.g. re-login).
    if (isAuthenticated) {
      redirectedRef.current = false;
    }
  }, [authReady, isAuthenticated, router]);

  // During Firebase init, show a full-screen spinner.
  // Do NOT redirect during this window.
  if (!authReady) {
    return (
      <div className="flex flex-col items-center justify-center h-screen gap-4"
        style={{ background: "#0a0f1e" }}>
        <div className="w-14 h-14 rounded-2xl flex items-center justify-center"
          style={{ background: "linear-gradient(135deg, #0891b2 0%, #7c3aed 100%)" }}>
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
            <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="#fff" strokeWidth="1.5" strokeLinejoin="round" />
            <path d="M2 17l10 5 10-5" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M2 12l10 5 10-5" stroke="rgba(255,255,255,0.5)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <div className="spinner" />
        <p className="text-xs" style={{ color: "#334155" }}>Verifying session…</p>
      </div>
    );
  }

  // Auth is ready but not authenticated — render nothing while redirect fires.
  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="flex min-h-screen" style={{ background: "#0a0f1e" }}>
      <Sidebar />
      <main className="flex-1 min-h-screen overflow-y-auto md:ml-64">
        {children}
      </main>
    </div>
  );
}
