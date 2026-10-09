"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "../../../lib/auth";
import TopBar from "../../../components/TopBar";

// ─── Types ────────────────────────────────────────────────────────────────────
interface DGUser {
  id: number;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function roleColor(role: string): string {
  if (role === "admin")   return "#a78bfa";
  if (role === "analyst") return "#06b6d4";
  return "#64748b";
}

function Skeleton() {
  return (
    <tr>
      {Array.from({ length: 6 }).map((_, i) => (
        <td key={i}>
          <div
            className="h-4 rounded animate-pulse"
            style={{ background: "rgba(26,39,68,0.8)", width: i === 0 ? "80px" : "60px" }}
          />
        </td>
      ))}
    </tr>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────
export default function UsersPage() {
  const [users, setUsers]     = useState<DGUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState("");
  const [toggling, setToggling] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/api/users");
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail ?? `HTTP ${res.status}`);
      }
      setUsers(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function toggleUser(id: number) {
    setToggling(id);
    try {
      const res = await apiFetch(`/api/users/${id}/toggle`, { method: "PATCH" });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail ?? `HTTP ${res.status}`);
      }
      const updated: DGUser = await res.json();
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Toggle failed");
    } finally {
      setToggling(null);
    }
  }

  const activeCount = users.filter((u) => u.is_active).length;

  return (
    <div className="min-h-screen">
      <TopBar title="User Management" subtitle="Security team accounts and roles">
        <button
          className="btn-ghost text-xs"
          onClick={load}
          disabled={loading}
          style={{ opacity: loading ? 0.5 : 1 }}
        >
          ↻ Refresh
        </button>
      </TopBar>

      <div className="p-6 animate-fade-up space-y-6">

        {/* RBAC overview cards */}
        <div className="grid grid-cols-3 gap-3">
          {[
            {
              role: "ADMIN",
              color: "#a78bfa",
              icon: "👑",
              perms: ["Manage users", "System config", "All policies", "All incidents"],
            },
            {
              role: "ANALYST",
              color: "#06b6d4",
              icon: "🔍",
              perms: ["View incidents", "Investigate", "Manage alerts", "View events"],
            },
            {
              role: "VIEWER",
              color: "#64748b",
              icon: "👁",
              perms: ["Read-only dashboard", "View reports", "No config access"],
            },
          ].map((r) => (
            <div
              key={r.role}
              className="dg-card"
              style={{ border: `1px solid ${r.color}20` }}
            >
              <div className="flex items-center gap-2 mb-3">
                <span className="text-lg">{r.icon}</span>
                <span className="text-xs font-bold" style={{ color: r.color }}>
                  {r.role}
                </span>
                <span
                  className="ml-auto text-xs font-bold px-2 py-0.5 rounded-full"
                  style={{ background: `${r.color}15`, color: r.color }}
                >
                  {users.filter((u) => u.role === r.role.toLowerCase()).length}
                </span>
              </div>
              <div className="space-y-1.5">
                {r.perms.map((p) => (
                  <div
                    key={p}
                    className="flex items-center gap-1.5 text-xs"
                    style={{ color: "#475569" }}
                  >
                    <span style={{ color: r.color, fontSize: "10px" }}>✓</span> {p}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Stats bar */}
        <div className="flex items-center gap-4 text-xs" style={{ color: "#475569" }}>
          <span>
            <span className="font-bold" style={{ color: "#e2e8f0" }}>{users.length}</span> total users
          </span>
          <span>·</span>
          <span>
            <span className="font-bold" style={{ color: "#34d058" }}>{activeCount}</span> active
          </span>
          <span>·</span>
          <span>
            <span className="font-bold" style={{ color: "#ff3b3b" }}>
              {users.length - activeCount}
            </span>{" "}
            inactive
          </span>
        </div>

        {/* Error banner */}
        {error && (
          <div
            className="flex items-center justify-between px-4 py-3 rounded-xl text-sm"
            style={{
              background: "rgba(255,59,59,0.06)",
              border: "1px solid rgba(255,59,59,0.2)",
              color: "#ff3b3b",
            }}
          >
            <span>⚠ {error}</span>
            <button
              className="btn-ghost text-xs ml-4"
              onClick={load}
            >
              Retry
            </button>
          </div>
        )}

        {/* Users table */}
        <div className="dg-card p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full data-table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} />)
                ) : users.length === 0 && !error ? (
                  <tr>
                    <td colSpan={6}>
                      <div
                        className="flex flex-col items-center justify-center py-12"
                        style={{ color: "#1e3a5f" }}
                      >
                        <span className="text-4xl mb-3">👤</span>
                        <p className="text-sm">No users found</p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  users.map((u) => (
                    <tr key={u.id}>
                      {/* Username */}
                      <td>
                        <div className="flex items-center gap-2">
                          <div
                            className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
                            style={{
                              background: `${roleColor(u.role)}20`,
                              color: roleColor(u.role),
                            }}
                          >
                            {u.username[0].toUpperCase()}
                          </div>
                          <span className="font-mono text-xs text-white">
                            {u.username}
                          </span>
                        </div>
                      </td>

                      {/* Email */}
                      <td>
                        <span className="text-xs" style={{ color: "#64748b" }}>
                          {u.email || "—"}
                        </span>
                      </td>

                      {/* Role */}
                      <td>
                        <span
                          className="text-[10px] px-2 py-0.5 rounded font-bold"
                          style={{
                            background: `${roleColor(u.role)}15`,
                            color: roleColor(u.role),
                          }}
                        >
                          {u.role.toUpperCase()}
                        </span>
                      </td>

                      {/* Status */}
                      <td>
                        <div className="flex items-center gap-1.5">
                          <span
                            className="w-1.5 h-1.5 rounded-full"
                            style={{
                              background: u.is_active ? "#10b981" : "#ef4444",
                              boxShadow: u.is_active ? "0 0 4px #10b981" : "none",
                            }}
                          />
                          <span
                            className="text-xs"
                            style={{ color: u.is_active ? "#10b981" : "#ef4444" }}
                          >
                            {u.is_active ? "Active" : "Inactive"}
                          </span>
                        </div>
                      </td>

                      {/* Created */}
                      <td>
                        <span
                          className="font-mono text-[10px]"
                          style={{ color: "#334155" }}
                        >
                          {u.created_at
                            ? new Date(u.created_at).toLocaleDateString([], {
                                year: "numeric",
                                month: "short",
                                day: "2-digit",
                              })
                            : "—"}
                        </span>
                      </td>

                      {/* Actions */}
                      <td>
                        <button
                          disabled={toggling === u.id}
                          onClick={() => toggleUser(u.id)}
                          className="text-[10px] py-1 px-2.5 rounded transition-all"
                          style={{
                            color: u.is_active ? "#ef4444" : "#10b981",
                            background: "none",
                            border: `1px solid ${u.is_active ? "rgba(239,68,68,0.2)" : "rgba(16,185,129,0.2)"}`,
                            fontFamily: "inherit",
                            cursor: toggling === u.id ? "wait" : "pointer",
                            opacity: toggling === u.id ? 0.5 : 1,
                          }}
                        >
                          {toggling === u.id
                            ? "…"
                            : u.is_active
                            ? "Disable"
                            : "Enable"}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Footer */}
          {!loading && users.length > 0 && (
            <div
              className="px-4 py-2.5 border-t flex items-center justify-between"
              style={{ borderColor: "rgba(99,179,237,0.06)" }}
            >
              <span className="text-xs" style={{ color: "#334155" }}>
                {users.length} user{users.length !== 1 ? "s" : ""} · live from API
              </span>
              <span
                className="text-[10px] font-mono"
                style={{ color: "#1e3a5f" }}
              >
                RBAC enforced · Audit logged
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
