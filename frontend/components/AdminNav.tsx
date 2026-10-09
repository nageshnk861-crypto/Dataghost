"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import { useAuthContext } from "@/lib/AuthContext";
import { useSidebarOpen, toggleSidebar } from "./Sidebar";

interface AdminNavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
  description?: string;
}

const ADMIN_NAV_ITEMS: AdminNavItem[] = [
  {
    href: "/admin/provisioning",
    label: "Device Provisioning",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
        <rect x="2" y="3" width="20" height="14" rx="2" stroke="currentColor" strokeWidth="1.5" />
        <path d="M8 21h8M12 17v4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <circle cx="12" cy="9" r="1.5" fill="currentColor" />
      </svg>
    ),
    description: "Create and manage device provisioning records",
  },
  {
    href: "/admin/devices",
    label: "Enrolled Devices",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.5" />
        <path d="M12 7v5l3.5 1.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
    description: "View and manage enrolled devices",
  },
  {
    href: "/admin/enrollment-policies",
    label: "Enrollment Policies",
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" stroke="currentColor" strokeWidth="1.5" />
        <path d="M14 2v6h6M9 12h6M9 16h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    description: "Create and manage enrollment policies",
  },
];

export default function AdminNav() {
  const pathname = usePathname();
  const { user, logout } = useAuthContext();
  const [open, setOpen] = useSidebarOpen();
  const [mounted, setMounted] = useState(false);

  // Prevent hydration mismatch
  useEffect(() => {
    setMounted(true);
  }, []);

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
      {/* Mobile backdrop overlay */}
      {open && (
        <div
          className="fixed inset-0 z-30 md:hidden"
          style={{ background: "rgba(3,7,18,0.7)", backdropFilter: "blur(4px)" }}
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Admin sidebar panel */}
      <aside
        className={[
          "fixed left-0 top-0 h-screen w-64 flex flex-col",
          "transition-transform duration-300 ease-in-out",
          open ? "translate-x-0" : "-translate-x-full",
          "md:translate-x-0",
        ].join(" ")}
        style={{
          background: "#0a0f1e",
          borderRight: "1px solid #1a2744",
          zIndex: 40,
        }}
        aria-label="Admin navigation"
      >
        {/* Logo & Header */}
        <div className="px-5 py-5 border-b flex items-center justify-between" style={{ borderColor: "#1a2744" }}>
          <div className="flex items-center gap-3">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center text-xl"
              style={{
                background: "linear-gradient(135deg, #7c3aed, #a855f7)",
                border: "1px solid rgba(168,85,247,0.3)",
              }}
            >
              ⚙️
            </div>
            <div>
              <p className="text-sm font-bold" style={{ color: "#a855f7" }}>DataGhost Admin</p>
              <p className="text-[10px] font-medium" style={{ color: "#94a3b8" }}>Management</p>
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
          {ADMIN_NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href + "/");

            return (
              <Link
                key={item.href}
                href={item.href}
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 group"
                style={
                  isActive
                    ? {
                        background: "rgba(168,85,247,0.08)",
                        color: "#a855f7",
                        borderLeft: "2px solid #a855f7",
                        paddingLeft: "calc(0.75rem - 2px)",
                      }
                    : {
                        color: "#94a3b8",
                        borderLeft: "2px solid transparent",
                        paddingLeft: "calc(0.75rem - 2px)",
                      }
                }
                title={item.description}
              >
                <span
                  className="flex-shrink-0"
                  style={{ color: isActive ? "#a855f7" : "#94a3b8" }}
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
          {/* Admin info */}
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
                style={{ background: "linear-gradient(135deg, #a855f7, #d946ef)" }}
              >
                {mounted && (user?.username || "A")[0]}
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold text-white truncate">
                  {mounted && (user?.username || "Admin")}
                </p>
                <p className="text-[10px] text-slate-400 capitalize">
                  {mounted && (user?.role || "admin")}
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

          {/* Admin status badge */}
          <div
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg"
            style={{
              background: "rgba(168,85,247,0.06)",
              border: "1px solid rgba(168,85,247,0.15)",
            }}
          >
            <span
              className="w-2 h-2 rounded-full flex-shrink-0 animate-pulse"
              style={{ background: "#a855f7" }}
            />
            <div className="flex-1 min-w-0">
              <p className="text-[10px] font-semibold" style={{ color: "#a855f7" }}>Admin Access</p>
              <p className="text-[9px]" style={{ color: "#475569" }}>Full control enabled</p>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
