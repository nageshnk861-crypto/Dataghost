"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  {
    href: "/dashboard",
    label: "Dashboard",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
        <rect x="3" y="3" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    ),
  },
  {
    href: "/scanner",
    label: "Scanner",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
        <circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="1.5" />
        <path d="M21 21l-4.35-4.35" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    href: "/incidents",
    label: "Incidents",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
        <path
          d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
          stroke="currentColor"
          strokeWidth="1.5"
        />
        <path d="M12 9v4M12 17h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    href: "/devices",
    label: "Devices",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
        <rect x="2" y="3" width="20" height="14" rx="2" stroke="currentColor" strokeWidth="1.5" />
        <path d="M8 21h8M12 17v4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    href: "/analytics",
    label: "Analytics",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
        <path d="M18 20V10M12 20V4M6 20v-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    href: "/events",
    label: "Events",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
];

import { useAuthContext } from "../lib/AuthContext";

// ── Hamburger button rendered in each page's top-bar on mobile ──────────────
export function MobileMenuButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Open navigation menu"
      className="md:hidden flex items-center justify-center w-8 h-8 rounded-lg transition-colors"
      style={{ color: "#94a3b8", background: "rgba(26,39,68,0.5)", border: "1px solid #1a2744" }}
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
        <path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
      </svg>
    </button>
  );
}

// ── Sidebar state managed via a tiny module-level signal ─────────────────────
// We use a simple event emitter so MobileMenuButton (used inside page headers)
// can open the sidebar without prop-drilling through every page.
type Listener = (open: boolean) => void;
const listeners = new Set<Listener>();
let _sidebarOpen = false;

export function toggleSidebar() {
  _sidebarOpen = !_sidebarOpen;
  listeners.forEach((l) => l(_sidebarOpen));
}

export function useSidebarOpen() {
  const [open, setOpen] = useState(_sidebarOpen);
  useEffect(() => {
    const handler: Listener = (v) => setOpen(v);
    listeners.add(handler);
    return () => { listeners.delete(handler); };
  }, []);
  return [open, (v: boolean) => {
    _sidebarOpen = v;
    listeners.forEach((l) => l(v));
  }] as const;
}

// ── Main Sidebar component ───────────────────────────────────────────────────
export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuthContext();
  const [open, setOpen] = useSidebarOpen();

  // Close sidebar on route change (mobile)
  useEffect(() => {
    setOpen(false);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [setOpen]);

  return (
    <>
      {/* ── Mobile backdrop overlay ─────────────────────────────────────── */}
      {open && (
        <div
          className="fixed inset-0 z-30 md:hidden"
          style={{ background: "rgba(3,7,18,0.7)", backdropFilter: "blur(4px)" }}
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* ── Sidebar panel ───────────────────────────────────────────────── */}
      <aside
        className={[
          "fixed left-0 top-0 h-screen w-64 flex flex-col",
          "transition-transform duration-300 ease-in-out",
          // Mobile: slide in/out; Desktop: always visible
          open ? "translate-x-0" : "-translate-x-full",
          "md:translate-x-0",
        ].join(" ")}
        style={{
          background: "#0a0f1e",
          borderRight: "1px solid #1a2744",
          zIndex: 40,
        }}
        aria-label="Main navigation"
      >
        {/* Logo */}
        <div className="px-5 py-5 border-b flex items-center justify-between" style={{ borderColor: "#1a2744" }}>
          <div className="flex items-center gap-3">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center text-xl"
              style={{
                background: "linear-gradient(135deg, #0089b2, #00d4ff22)",
                border: "1px solid rgba(0,212,255,0.3)",
              }}
            >
              👻
            </div>
            <div>
              <p className="text-sm font-bold" style={{ color: "#00d4ff" }}>DataGhost</p>
              <p className="text-[10px] font-medium" style={{ color: "#94a3b8" }}>DLP Platform</p>
            </div>
          </div>

          {/* Close button — mobile only */}
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="md:hidden flex items-center justify-center w-7 h-7 rounded-lg text-slate-400 hover:text-white transition-colors"
            style={{ background: "rgba(26,39,68,0.5)", border: "1px solid #1a2744" }}
            aria-label="Close menu"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href + "/");

            return (
              <Link
                key={item.href}
                href={item.href}
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150"
                style={
                  isActive
                    ? {
                        background: "rgba(0,212,255,0.08)",
                        color: "#00d4ff",
                        borderLeft: "2px solid #00d4ff",
                        paddingLeft: "calc(0.75rem - 2px)",
                      }
                    : {
                        color: "#94a3b8",
                        borderLeft: "2px solid transparent",
                        paddingLeft: "calc(0.75rem - 2px)",
                      }
                }
              >
                <span
                  className="flex-shrink-0"
                  style={{ color: isActive ? "#00d4ff" : "#94a3b8" }}
                >
                  {item.icon}
                </span>
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Bottom section */}
        <div className="px-4 py-3 border-t space-y-2.5" style={{ borderColor: "#1a2744" }}>
          {/* User Card & Logout */}
          <div
            className="flex items-center justify-between px-3 py-2 rounded-lg"
            style={{
              background: "rgba(15, 23, 42, 0.7)",
              border: "1px solid rgba(30, 41, 59, 0.8)",
            }}
          >
            <div className="flex items-center gap-2.5 min-w-0">
              <div
                className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white uppercase"
                style={{ background: "linear-gradient(135deg, #0891b2, #7c3aed)" }}
              >
                {(user?.username || "U")[0]}
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold text-white truncate">
                  {user?.username || "User"}
                </p>
                <p className="text-[10px] text-slate-400 capitalize">
                  {user?.role || "authenticated"}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => void logout()}
              title="Sign Out"
              className="p-1.5 rounded-md text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-colors cursor-pointer"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
                <path
                  d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"
                  stroke="currentColor"
                  strokeWidth="1.75"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </div>

          {/* Agent status */}
          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg"
            style={{
              background: "rgba(52,208,88,0.06)",
              border: "1px solid rgba(52,208,88,0.15)",
            }}
          >
            <span
              className="w-2 h-2 rounded-full flex-shrink-0 animate-pulse"
              style={{ background: "#34d058" }}
            />
            <div className="flex-1 min-w-0">
              <p className="text-[10px] font-semibold" style={{ color: "#34d058" }}>DataGhost Agent</p>
              <p className="text-[9px]" style={{ color: "#475569" }}>Monitoring active</p>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
