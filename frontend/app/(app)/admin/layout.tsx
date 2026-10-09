"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuthContext } from "@/lib/AuthContext";
import AdminNav from "@/components/AdminNav";
import TopBar from "@/components/TopBar";

interface Breadcrumb {
  label: string;
  href?: string;
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { authReady, isAuthenticated, user } = useAuthContext();
  const redirectedRef = useRef(false);

  // Check if user is admin
  const isAdmin = user?.role === "admin";

  useEffect(() => {
    if (authReady && (!isAuthenticated || !isAdmin) && !redirectedRef.current) {
      redirectedRef.current = true;
      router.replace("/dashboard");
    }
  }, [authReady, isAuthenticated, isAdmin, router]);

  // Show loading state during auth check
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
        <p className="text-xs" style={{ color: "#334155" }}>Loading admin dashboard…</p>
      </div>
    );
  }

  // Not authenticated or not admin — render nothing while redirect fires
  if (!isAuthenticated || !isAdmin) {
    return null;
  }

  return (
    <div className="flex min-h-screen" style={{ background: "#0a0f1e" }}>
      <AdminNav />
      <main className="flex-1 min-h-screen overflow-y-auto md:ml-64">
        <TopBar title="Admin Dashboard" subtitle="Organization & Device Management" />
        {children}
      </main>
    </div>
  );
}
