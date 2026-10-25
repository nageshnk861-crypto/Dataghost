"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "../../../lib/auth";
import TopBar from "../../../components/TopBar";
import { WakeUpBanner, ErrorBanner } from "@/components/Banners";

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

function roleIcon(role: string): string {
  if (role === "admin")   return "👑";
  if (role === "analyst") return "🔍";
  return "👁";
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

// ─── Create User Modal ────────────────────────────────────────────────────────
interface CreateUserModalProps {
  onClose: () => void;
  onCreated: (user: DGUser) => void;
}

function CreateUserModal({ onClose, onCreated }: CreateUserModalProps) {
  const [form, setForm] = useState({ username: "", email: "", password: "", role: "analyst" });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setErr("");
    try {
      const res = await apiFetch("/api/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail ?? `HTTP ${res.status}`); }
      const created: DGUser = await res.json();
      onCreated(created); onClose();
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Failed to create user"); }
    finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="w-full max-w-md rounded-2xl p-6 shadow-2xl"
        style={{ background: "#0d1526", border: "1px solid rgba(99,179,237,0.15)" }}>
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-base font-bold text-white">Create User</h2>
            <p className="text-xs mt-0.5" style={{ color: "#475569" }}>Add a new security team member</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-lg leading-none">✕</button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          {([ ["username","Username","text","e.g. jsmith",3,64], ["email","Email","email","user@company.com",0,0], ["password","Password","password","Minimum 6 characters",6,0] ] as [keyof typeof form, string, string, string, number, number][]).map(([k, label, type, ph, min]) => (
            <div key={k}>
              <label className="block text-xs font-medium mb-1" style={{ color: "#64748b" }}>{label}</label>
              <input required type={type} minLength={min || undefined} value={form[k]}
                onChange={(e) => setForm((f) => ({ ...f, [k]: e.target.value }))}
                placeholder={ph}
                className="w-full px-3 py-2 rounded-lg text-sm text-white focus:outline-none"
                style={{ background: "rgba(26,39,68,0.6)", border: "1px solid rgba(99,179,237,0.15)" }} />
            </div>
          ))}
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "#64748b" }}>Role</label>
            <select value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
              className="w-full px-3 py-2 rounded-lg text-sm text-white focus:outline-none"
              style={{ background: "rgba(26,39,68,0.6)", border: "1px solid rgba(99,179,237,0.15)" }}>
              <option value="analyst">Analyst — Investigate &amp; respond</option>
              <option value="admin">Admin — Full system access</option>
              <option value="viewer">Viewer — Read-only access</option>
            </select>
          </div>
          {err && <p className="text-xs px-3 py-2 rounded-lg" style={{ background: "rgba(239,68,68,0.08)", color: "#f87171", border: "1px solid rgba(239,68,68,0.2)" }}>⚠ {err}</p>}
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="flex-1 py-2 rounded-lg text-sm font-medium"
              style={{ background: "rgba(26,39,68,0.5)", color: "#64748b", border: "1px solid rgba(99,179,237,0.1)" }}>Cancel</button>
            <button type="submit" disabled={saving} className="flex-1 py-2 rounded-lg text-sm font-semibold text-white hover:brightness-110"
              style={{ background: "linear-gradient(135deg, #7c3aed, #a78bfa)", opacity: saving ? 0.7 : 1 }}>
              {saving ? "Creating…" : "Create User"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Role Change Modal ────────────────────────────────────────────────────────
interface RoleModalProps { user: DGUser; onClose: () => void; onUpdated: (u: DGUser) => void; }

function RoleModal({ user, onClose, onUpdated }: RoleModalProps) {
  const [role, setRole] = useState(user.role);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setErr("");
    try {
      const res = await apiFetch(`/api/users/${user.id}/role`, {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role }),
      });
      if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail ?? `HTTP ${res.status}`); }
      onUpdated(await res.json()); onClose();
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Failed to update role"); }
    finally { setSaving(false); }
  }

  const ROLES = [
    { value: "admin",   label: "Admin",   desc: "Full system access, user management, all policies", icon: "👑", color: "#a78bfa" },
    { value: "analyst", label: "Analyst", desc: "Investigate incidents, manage alerts, view events",  icon: "🔍", color: "#06b6d4" },
    { value: "viewer",  label: "Viewer",  desc: "Read-only dashboard access, no config changes",     icon: "👁", color: "#64748b" },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(4px)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="w-full max-w-sm rounded-2xl p-6 shadow-2xl"
        style={{ background: "#0d1526", border: "1px solid rgba(99,179,237,0.15)" }}>
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-base font-bold text-white">Change Role</h2>
            <p className="text-xs mt-0.5" style={{ color: "#475569" }}>Update access level for <span className="font-mono" style={{ color: "#94a3b8" }}>{user.username}</span></p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-lg leading-none">✕</button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            {ROLES.map((r) => (
              <label key={r.value} className="flex items-start gap-3 p-3 rounded-lg cursor-pointer transition-all"
                style={{ background: role === r.value ? `${r.color}10` : "rgba(15,23,42,0.4)", border: `1px solid ${role === r.value ? `${r.color}40` : "rgba(99,179,237,0.08)"}` }}>
                <input type="radio" name="role" value={r.value} checked={role === r.value} onChange={() => setRole(r.value)} className="mt-0.5" />
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm">{r.icon}</span>
                    <span className="text-xs font-bold" style={{ color: r.color }}>{r.label}</span>
                  </div>
                  <p className="text-[11px] mt-0.5" style={{ color: "#475569" }}>{r.desc}</p>
                </div>
              </label>
            ))}
          </div>
          {err && <p className="text-xs px-3 py-2 rounded-lg" style={{ background: "rgba(239,68,68,0.08)", color: "#f87171", border: "1px solid rgba(239,68,68,0.2)" }}>⚠ {err}</p>}
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="flex-1 py-2 rounded-lg text-sm font-medium"
              style={{ background: "rgba(26,39,68,0.5)", color: "#64748b", border: "1px solid rgba(99,179,237,0.1)" }}>Cancel</button>
            <button type="submit" disabled={saving || role === user.role} className="flex-1 py-2 rounded-lg text-sm font-semibold text-white hover:brightness-110"
              style={{ background: "linear-gradient(135deg, #0891b2, #06b6d4)", opacity: (saving || role === user.role) ? 0.5 : 1 }}>
              {saving ? "Saving…" : "Apply Role"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────
export default function UsersPage() {
  const [users, setUsers]     = useState<DGUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [isWakingUp, setIsWakingUp] = useState(false);
  const [error, setError]     = useState("");
  const [toggling, setToggling] = useState<number | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [roleModalUser, setRoleModalUser] = useState<DGUser | null>(null);

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
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold text-white transition-all hover:brightness-110"
          style={{ background: "linear-gradient(135deg, #7c3aed, #a78bfa)", border: "1px solid rgba(167,139,250,0.3)" }}
        >
          <span className="font-bold text-sm">+</span> Add User
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

        {/* Wake-up banner */}
        {isWakingUp && <WakeUpBanner onRetry={load} />}

        {/* Error banner */}
        {error && <ErrorBanner message={error} onRetry={load} />}

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
                          {roleIcon(u.role)} {u.role.toUpperCase()}
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
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() => setRoleModalUser(u)}
                            className="text-[10px] py-1 px-2.5 rounded transition-all"
                            style={{ color: "#a78bfa", background: "none", border: "1px solid rgba(167,139,250,0.2)", fontFamily: "inherit", cursor: "pointer" }}
                            title="Change user role"
                          >
                            Role
                          </button>
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
                            {toggling === u.id ? "…" : u.is_active ? "Disable" : "Enable"}
                          </button>
                        </div>
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

      {/* Modals */}
      {showCreateModal && (
        <CreateUserModal
          onClose={() => setShowCreateModal(false)}
          onCreated={(u) => setUsers((prev) => [...prev, u])}
        />
      )}
      {roleModalUser && (
        <RoleModal
          user={roleModalUser}
          onClose={() => setRoleModalUser(null)}
          onUpdated={(u) => {
            setUsers((prev) => prev.map((x) => (x.id === u.id ? u : x)));
            setRoleModalUser(null);
          }}
        />
      )}
    </div>
  );
}
