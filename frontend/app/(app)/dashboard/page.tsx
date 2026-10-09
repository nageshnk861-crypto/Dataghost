"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import TopBar from "../../../components/TopBar";
import { fetchDashboardStats, fetchDashboardActivity, fetchIncidents } from "@/lib/api";
import type { DashboardStats, ActivityDataPoint, RiskSegment, IncidentRow } from "@/lib/api";
import { useAuthContext } from "@/lib/AuthContext";
import { AuthError } from "@/lib/auth";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, BarChart, Bar, Legend,
} from "recharts";

// ─── Helpers ──────────────────────────────────────────────────────────────────
function severityColor(s: string) {
  if (s === "CRITICAL") return "#ef4444";
  if (s === "HIGH") return "#f59e0b";
  if (s === "MEDIUM") return "#60a5fa";
  return "#10b981";
}

function RiskBar({ score, severity }: { score: number; severity: string }) {
  const color = severityColor(severity);
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full" style={{ background: "rgba(30,58,95,0.5)" }}>
        <div
          className="h-1.5 rounded-full transition-all"
          style={{ width: `${score}%`, background: color }}
        />
      </div>
      <span className="font-mono text-[11px] w-6 text-right" style={{ color }}>{score}</span>
    </div>
  );
}

const PIE_COLORS = ["#10b981", "#60a5fa", "#f59e0b", "#ef4444"];
const CLASS_LABELS = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"];

// Build risk distribution from incidents array
function buildRiskSegments(incidents: IncidentRow[]): RiskSegment[] {
  const counts: Record<string, number> = { LOW: 0, MEDIUM: 0, HIGH: 0, CRITICAL: 0 };
  for (const inc of incidents) {
    const sev = inc.severity?.toUpperCase();
    if (sev in counts) counts[sev]++;
    else counts["LOW"]++;
  }
  const colorMap: Record<string, string> = {
    CRITICAL: "#ef4444",
    HIGH: "#f59e0b",
    MEDIUM: "#60a5fa",
    LOW: "#10b981",
  };
  return Object.entries(counts)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value, color: colorMap[name] }));
}

// Build classification breakdown from incidents
function buildClassData(incidents: IncidentRow[]) {
  const counts: Record<string, number> = {
    PUBLIC: 0, INTERNAL: 0, CONFIDENTIAL: 0, RESTRICTED: 0,
  };
  for (const inc of incidents) {
    const cls = inc.classification?.toUpperCase();
    if (cls && cls in counts) counts[cls]++;
  }
  return CLASS_LABELS.map((l) => ({ name: l, value: counts[l] }));
}

// ─── Component ────────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const { signalAuthFailure } = useAuthContext();

  const [stats, setStats]       = useState<DashboardStats | null>(null);
  const [activity, setActivity] = useState<ActivityDataPoint[]>([]);
  const [incidents, setIncidents] = useState<IncidentRow[]>([]);
  // initialLoading: true only on the very first load (shows skeletons).
  const [initialLoading, setInitialLoading] = useState(true);
  // dataError: shown inside the dashboard without destroying the shell.
  const [dataError, setDataError] = useState<string | null>(null);
  const [now, setNow] = useState(new Date());

  // Use a ref so the polling callback always reads the latest value without
  // being recreated (avoids cancelling/restarting the interval on every render).
  const authFailedRef = useRef(false);
  const intervalRef   = useRef<ReturnType<typeof setInterval> | null>(null);

  // Clock — independent, always running.
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  // Stable load function — created once, reads refs for mutable values.
  const load = useCallback(async (isInitial = false) => {
    if (authFailedRef.current) return; // Auth is dead — stop silently.

    try {
      setDataError(null);
      const [statsData, activityData, incidentsData] = await Promise.all([
        fetchDashboardStats(),
        fetchDashboardActivity(),
        fetchIncidents({ page: 1, per_page: 100 }),
      ]);
      setStats(statsData);
      setActivity(activityData);
      setIncidents(incidentsData.items);
    } catch (err) {
      if (err instanceof AuthError) {
        // JWT rejected by backend — clear interval, signal auth failure once.
        authFailedRef.current = true;
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
        signalAuthFailure(); // Clears auth state → layout redirects to /login ONCE.
      } else {
        // Network/server error — show in-dashboard error, keep polling.
        setDataError(
          err instanceof Error ? err.message : "Failed to load dashboard data"
        );
      }
    } finally {
      if (isInitial) setInitialLoading(false);
    }
  }, [signalAuthFailure]); // signalAuthFailure is stable (useCallback with []).

  // Mount: initial load + 30s polling. Single interval, proper cleanup.
  useEffect(() => {
    load(true); // Initial load — shows skeletons until complete.
    intervalRef.current = setInterval(() => load(false), 30_000);
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [load]); // `load` is stable — this effect runs exactly once.

  const riskSegments = buildRiskSegments(incidents);
  const classData = buildClassData(incidents);

  const statCards = [
    {
      label: "Protected Devices",
      value: stats?.protected_devices ?? "—",
      sub: "Active agents",
      icon: "🖥",
      color: "#06b6d4",
    },
    {
      label: "Files Scanned",
      value: stats?.files_scanned?.toLocaleString() ?? "—",
      sub: "Total lifetime",
      icon: "📁",
      color: "#3b82f6",
    },
    {
      label: "Sensitive Files",
      value: stats?.sensitive_files?.toLocaleString() ?? "—",
      sub: "Risk score ≥ 30",
      icon: "⚠",
      color: "#f59e0b",
    },
    {
      label: "Blocked Transfers",
      value: stats?.blocked_transfers ?? "—",
      sub: "Prevented leaks",
      icon: "🚫",
      color: "#ef4444",
    },
    {
      label: "Critical Incidents",
      value: stats?.critical_incidents ?? "—",
      sub: "Require review",
      icon: "🔴",
      color: "#a855f7",
    },
  ];

  return (
    <div className="min-h-screen">
      <TopBar
        title="Security Operations Center"
        subtitle="Real-time data loss prevention monitoring"
      >
        <div className="font-mono text-xs" style={{ color: "#334155" }}>
          {now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
        </div>
        <div
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg"
          style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.15)" }}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs font-medium" style={{ color: "#34d399" }}>LIVE</span>
        </div>
      </TopBar>

      {initialLoading ? (
        <div className="p-6 space-y-6 animate-fade-up">
          {/* Skeleton stat cards */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="stat-card">
                <div className="h-4 w-24 animate-pulse rounded mb-2" style={{ background: "rgba(26,39,68,0.8)" }} />
                <div className="h-8 w-16 animate-pulse rounded" style={{ background: "rgba(26,39,68,0.8)" }} />
              </div>
            ))}
          </div>
          {/* Skeleton chart area */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2 dg-card h-64 animate-pulse" style={{ background: "rgba(26,39,68,0.4)" }} />
            <div className="dg-card h-64 animate-pulse" style={{ background: "rgba(26,39,68,0.4)" }} />
          </div>
        </div>
      ) : (
        <div className="p-6 space-y-6 animate-fade-up">

          {/* Error banner — shown inside dashboard, not replacing it */}
          {dataError && (
            <div
              className="px-4 py-3 rounded-lg text-sm flex items-center justify-between gap-4"
              style={{
                background: "rgba(255,59,59,0.06)",
                border: "1px solid rgba(255,59,59,0.2)",
                color: "#ff3b3b",
              }}
            >
              <span>⚠ {dataError}</span>
              <button
                onClick={() => load(false)}
                className="text-xs px-3 py-1 rounded font-semibold flex-shrink-0"
                style={{
                  background: "rgba(255,59,59,0.12)",
                  border: "1px solid rgba(255,59,59,0.3)",
                  color: "#ff3b3b",
                  cursor: "pointer",
                }}
              >
                Retry
              </button>
            </div>
          )}

          {/* ── STAT CARDS ─────────────────────────────────────────────────── */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
            {statCards.map((c) => (
              <div key={c.label} className="stat-card">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-[11px] font-medium uppercase tracking-wide" style={{ color: "#475569" }}>
                      {c.label}
                    </p>
                    <p className="text-2xl font-bold mt-1" style={{ color: c.color }}>
                      {c.value}
                    </p>
                    <p className="text-[11px] mt-1" style={{ color: "#334155" }}>{c.sub}</p>
                  </div>
                  <span className="text-xl opacity-60">{c.icon}</span>
                </div>
              </div>
            ))}
          </div>

          {/* ── CHARTS ROW ─────────────────────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Area chart */}
            <div className="lg:col-span-2 dg-card">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-sm font-semibold text-white">7-Day Activity</p>
                  <p className="text-xs mt-0.5" style={{ color: "#475569" }}>
                    Scans, sensitive detections &amp; blocked transfers
                  </p>
                </div>
              </div>
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={activity} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gScans" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gSensitive" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gBlocked" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="date" tick={{ fill: "#334155", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: "#334155", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: "#0d1526", border: "1px solid rgba(99,179,237,0.15)", borderRadius: 8, fontSize: 12 }}
                    labelStyle={{ color: "#64748b" }}
                  />
                  <Area type="monotone" dataKey="scans" name="Scans" stroke="#3b82f6" fill="url(#gScans)" strokeWidth={1.5} />
                  <Area type="monotone" dataKey="sensitive" name="Sensitive" stroke="#f59e0b" fill="url(#gSensitive)" strokeWidth={1.5} />
                  <Area type="monotone" dataKey="blocked" name="Blocked" stroke="#ef4444" fill="url(#gBlocked)" strokeWidth={1.5} />
                  <Legend wrapperStyle={{ fontSize: 11, color: "#64748b" }} />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Risk distribution pie chart */}
            <div className="dg-card flex flex-col">
              <p className="text-sm font-semibold text-white mb-1">Risk Distribution</p>
              <p className="text-xs mb-4" style={{ color: "#475569" }}>By severity level</p>
              {riskSegments.length === 0 ? (
                <div className="flex-1 flex items-center justify-center">
                  <p className="text-sm" style={{ color: "#475569" }}>No data</p>
                </div>
              ) : (
                <>
                  <div className="flex-1 flex items-center justify-center">
                    <ResponsiveContainer width="100%" height={160}>
                      <PieChart>
                        <Pie
                          data={riskSegments}
                          dataKey="value"
                          nameKey="name"
                          cx="50%" cy="50%"
                          innerRadius={45}
                          outerRadius={70}
                          paddingAngle={3}
                        >
                          {riskSegments.map((seg, i) => (
                            <Cell key={i} fill={seg.color} />
                          ))}
                        </Pie>
                        <Tooltip
                          contentStyle={{ background: "#0d1526", border: "1px solid rgba(99,179,237,0.15)", borderRadius: 8, fontSize: 12 }}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="mt-2 space-y-1.5">
                    {riskSegments.map((seg) => (
                      <div key={seg.name} className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full" style={{ background: seg.color }} />
                          <span style={{ color: "#64748b" }}>{seg.name}</span>
                        </div>
                        <span className="font-mono" style={{ color: seg.color }}>{seg.value}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>

          {/* ── BOTTOM ROW ─────────────────────────────────────────────────── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Recent Threats */}
            <div className="dg-card">
              <p className="text-sm font-semibold text-white mb-4">⚡ Recent Threat Events</p>
              <div className="space-y-3">
                {(stats?.recent_threats ?? []).map((t, i) => (
                  <div key={i} className={`px-3 py-2.5 rounded-lg alert-${t.severity.toLowerCase()}`}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span
                        className="text-xs font-medium truncate max-w-[200px]"
                        style={{ color: severityColor(t.severity) }}
                      >
                        {t.filename || t.label || "—"}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold badge-${t.severity.toLowerCase()}`}
                      >
                        {t.severity}
                      </span>
                    </div>
                    <RiskBar score={t.risk_score ?? t.score ?? 0} severity={t.severity} />
                  </div>
                ))}
                {(!stats?.recent_threats || stats.recent_threats.length === 0) && (
                  <p className="text-xs text-center py-4" style={{ color: "#334155" }}>
                    No recent threats
                  </p>
                )}
              </div>
            </div>

            {/* Bar chart: blocked by day */}
            <div className="dg-card">
              <p className="text-sm font-semibold text-white mb-1">🚫 Blocked Transfers / Day</p>
              <p className="text-xs mb-4" style={{ color: "#475569" }}>
                Data exfiltration prevented this week
              </p>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={activity} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                  <XAxis dataKey="date" tick={{ fill: "#334155", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: "#334155", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: "#0d1526", border: "1px solid rgba(99,179,237,0.15)", borderRadius: 8, fontSize: 12 }}
                    labelStyle={{ color: "#64748b" }}
                  />
                  <Bar dataKey="blocked" name="Blocked" fill="#ef4444" fillOpacity={0.8} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="sensitive" name="Sensitive" fill="#f59e0b" fillOpacity={0.8} radius={[4, 4, 0, 0]} />
                  <Legend wrapperStyle={{ fontSize: 11, color: "#64748b" }} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* ── DATA CLASSIFICATION ────────────────────────────────────────── */}
          {classData.some((d) => d.value > 0) && (
            <div className="dg-card">
              <p className="text-sm font-semibold text-white mb-4">Data Classification Breakdown</p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {classData.map((c, i) => (
                  <div key={c.name} className="text-center p-4 rounded-lg" style={{ background: "rgba(15,23,42,0.5)" }}>
                    <p className="text-2xl font-bold" style={{ color: PIE_COLORS[i] }}>{c.value}</p>
                    <p className="text-xs mt-1" style={{ color: "#64748b" }}>{c.name}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── ZERO TRUST STATUS ──────────────────────────────────────────── */}
          <div
            className="dg-card"
            style={{ border: "1px solid rgba(124,58,237,0.15)", background: "rgba(124,58,237,0.04)" }}
          >
            <div className="flex items-center gap-3 mb-3">
              <div
                className="w-7 h-7 rounded-lg flex items-center justify-center"
                style={{ background: "rgba(124,58,237,0.15)" }}
              >
                <span className="text-sm">🛡</span>
              </div>
              <div>
                <p className="text-sm font-semibold" style={{ color: "#a78bfa" }}>Zero Trust Architecture</p>
                <p className="text-xs" style={{ color: "#475569" }}>Every request is verified · No implicit trust granted</p>
              </div>
              <div className="ml-auto flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-xs font-medium" style={{ color: "#34d399" }}>ENFORCED</span>
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {["Identity Verification", "Device Trust", "Data Classification", "Risk-Based Access"].map((item) => (
                <div
                  key={item}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg"
                  style={{ background: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.12)" }}
                >
                  <span className="text-emerald-400 text-xs">✓</span>
                  <span className="text-xs" style={{ color: "#64748b" }}>{item}</span>
                </div>
              ))}
            </div>
          </div>

        </div>
      )}
    </div>
  );
}
