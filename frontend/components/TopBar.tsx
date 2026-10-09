"use client";

import { useAuthContext } from "../lib/AuthContext";
import { toggleSidebar } from "./Sidebar";

interface Props {
  title: string;
  subtitle?: string;
  children?: React.ReactNode;
}

export default function TopBar({ title, subtitle, children }: Props) {
  const { logout } = useAuthContext();

  return (
    <div
      className="flex items-center justify-between px-4 md:px-6 py-4 sticky top-0"
      style={{
        background: "rgba(3, 7, 18, 0.85)",
        backdropFilter: "blur(12px)",
        borderBottom: "1px solid rgba(6, 182, 212, 0.07)",
        zIndex: 30,
      }}
    >
      <div className="flex items-center gap-3">
        {/* Hamburger — mobile only */}
        <button
          type="button"
          onClick={toggleSidebar}
          aria-label="Open navigation menu"
          className="md:hidden flex items-center justify-center w-8 h-8 rounded-lg transition-colors cursor-pointer"
          style={{ color: "#94a3b8", background: "rgba(26,39,68,0.5)", border: "1px solid rgba(6,182,212,0.15)" }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
          </svg>
        </button>
        <div>
          <h1 className="text-base font-bold text-white">{title}</h1>
          {subtitle && (
            <p className="text-xs mt-0.5" style={{ color: "#475569" }}>{subtitle}</p>
          )}
        </div>
      </div>
      <div className="flex items-center gap-3">
        {children}
        <button
          type="button"
          onClick={() => void logout()}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-all cursor-pointer"
          style={{ border: "1px solid rgba(148, 163, 184, 0.12)" }}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
            <path
              d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"
              stroke="currentColor"
              strokeWidth="1.75"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          Sign Out
        </button>
      </div>
    </div>
  );
}

