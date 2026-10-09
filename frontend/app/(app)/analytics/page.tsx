"use client";

import { useEffect, useState, useCallback } from "react";
import {
  fetchDashboardStats,
  fetchDashboardActivity,
  fetchIncidents,
} from "@/lib/api";
import type {
  DashboardStats,
  ActivityDataPoint,
  IncidentRow,
} from "@/lib/api";
import TopBar from "../../../components/TopBar";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  Legend,
} from "recharts";

const COLORS = ["#10b981", "#60a5fa", "#f59e0b", "#ef4444"];
const CLASS_LABELS = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"];

function riskColor(r: number) {
  if (r >= 76) return "#ef4444";
  if (r >= 51) return "#f59e0b";
  if (r >= 21) return "#60a5fa";
  return "#10b981";
}

// ─── Derive analytics from incidents list ────────────────────────────────────
function buildSevData(incidents: IncidentRow[]) {
  const counts: Record<string, number> = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
  for (const inc of incidents) {
    const sev = inc.severity?.toUpperCase();
    if (sev && sev in counts) counts[sev]++;
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
    .map(([name, value]) => ({
      name: name.charAt(0) + name.slice(1).toLowerCase(),
      value,
      color: colorMap[name],
    }));
}

function buildDestData(incidents: IncidentRow[]) {
  const counts: Record<string, number> = {};
  for (const inc of incidents) {
    const dest = inc.destination ?? "UNKNOWN";
    counts[dest] = (counts[dest] ?? 0) + 1;
  }
  const destColors: Record<string, string> = {
    EXTERNAL: "#ef4444",
    CLOUD: "#f59e0b",
    USB: "#a78bfa",
    INTERNAL: "#10b981",
    UNKNOWN: "#64748b",
  };
  return Object.entries(counts)
    .sort(([, a], [, b]) => b - a)
    .map(([name, value]) => ({
      name: name.charAt(0) + name.slice(1).toLowerCase(),
      value,
      color: destColors[name] ?? "#64748b",
    }));
}

function buildTopUsers(incidents: IncidentRow[]) {
  const userMap: Record<string, { count: number; totalRisk: number }> = {};
  for (const inc of incidents) {
    const user = inc.user ?? "unknown";
    if (!userMap[user]) userMap[user] = { count: 0, totalRisk: 0 };
    userMap[user].count++;
    userMap[user].totalRisk += inc.risk_score ?? 0;
  }
  return Object.entries(userMap)
    .map(([user, { count, totalRisk }]) => ({
      user,
      incidents: count,
      risk: Math.round(totalRisk / count),
    }))
    .sort((a, b) => b.incidents - a.incidents)
    .slice(0, 5);
}

function buildClassData(incidents: IncidentRow[]) {
  const counts: Record<string, number> = {
    PUBLIC: 0,
    INTERNAL: 0,
    CONFIDENTIAL: 0,
    RESTRICTED: 0,
  };
  for (const inc of incidents) {
    const cls = inc.classification?.toUpperCase();
    if (cls && cls in counts) counts[cls]++;
  }
  return CLASS_LABELS.map((l) => ({ name: l, value: counts[l] }));
}

function avgRiskScore(incidents: IncidentRow[]): number {
  if (incidents.length === 0) return 0;
  const sum = incidents.reduce((acc, inc) => acc + (inc.risk_score ?? 0), 0);
  return Math.round(sum / incidents.length);
}

// ─── Component ────────────────────────────────────────────────────────────────
export default function AnalyticsPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [activity, setActivity] = useState<ActivityDataPoint[]>([]);
  const [incidents, setIncidents] = useState<IncidentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statsData, activityData, incData] = await Promise.all([
        fetchDashboardStats(),
        fetchDashboardActivity(),
        fetchIncidents({ page: 1, per_page: 100 }),
      ]);
      setStats(statsData);
      setActivity(activityData);
      setIncidents(incData.items);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load analytics data"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const sevData = buildSevData(incidents);
  const destData = buildDestData(incidents);
  const topUsers = buildTopUsers(incidents);
  const classData = buildClassData(incidents);
  const avgRisk = avgRiskScore(incidents);

  const tooltipStyle = {
    contentStyle: {
      background: "#0d1526",
      border: "1px solid rgba(99,179,237,0.15)",
      borderRadius: 8,
      fontSize: 12,
    },
    labelStyle: { color: "#64748b" },
  };

  // KPI cards — all values derived from live incidents API data
  const blockedCount = incidents.filter(
    (inc) => inc.action_taken?.toUpperCase() === "BLOCKED"
  ).length;
  const blockedRate =
    incidents.length > 0
      ? Math.round((blockedCount / incidents.length) * 100)
      : 0;
  const criticalCount = incidents.filter(
    (inc) => inc.severity?.toUpperCase() === "CRITICAL"
  ).length;
  const criticalRate =
    incidents.length > 0
      ? Math.round((criticalCount / incidents.length) * 100)
      : 0;

  const kpiCards = [
    {
      label: "Avg Risk Score",
      value: avgRisk > 0 ? String(avgRisk) : incidents.length ? "0" : "—",
      sub: "Across sampled events",
      color: "#f59e0b",
      icon: "⚖",
    },
    {
      label: "Blocked Rate",
      value: incidents.length > 0 ? `${blockedRate}%` : "—",
      sub: "Transfers blocked",
      color: "#ef4444",
      icon: "🚫",
    },
    {
      label: "Critical Rate",
      value: incidents.length > 0 ? `${criticalRate}%` : "—",
      sub: "Critical severity share",
      color: "#f97316",
      icon: "🔴",
    },
    {
      label: "Incidents Sampled",
      value: incidents.length > 0 ? String(incidents.length) : "—",
      sub: `of ${stats?.files_scanned ?? "?"} files scanned`,
      color: "#06b6d4",
      icon: "📋",
    },
  ];

  return (
    <div className="min-h-screen">
      <TopBar title="Analytics" subtitle="Deep insights into data security posture" />

      {loading ? (
        <div className="flex items-center justify-center h-64 gap-3">
          <div className="spinner" />
          <span className="text-sm" style={{ color: "#475569" }}>
            Loading analytics…
          </span>
        </div>
      ) : (
        <div className="p-6 animate-fade-up space-y-6">

          {/* Error banner with Retry */}
          {error && (
            <div
              className="px-4 py-3 rounded-lg text-sm flex items-center justify-between gap-4"
              style={{
                background: "rgba(255,59,59,0.06)",
                border: "1px solid rgba(255,59,59,0.2)",
                color: "#ff3b3b",
              }}
            >
              <span>⚠ {error}</span>
              <button
                onClick={load}
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

          {/* KPI row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {kpiCards.map((k) => (
              <div key={k.label} className="stat-card">
                <div className="flex items-start justify-between">
                  <div>
                    <p
                      className="text-[11px] uppercase tracking-wide"
                      style={{ color: "#475569" }}
                    >
                      {k.label}
                    </p>
                    <p
                      className="text-2xl font-bold mt-1"
                      style={{ color: k.color }}
                    >
                      {k.value}
                    </p>
                    <p className="text-[11px] mt-1" style={{ color: "#334155" }}>
                      {k.sub}
                    </p>
                  </div>
                  <span className="text-xl opacity-60">{k.icon}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Charts row 1 */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Line chart: trend */}
            <div className="lg:col-span-2 dg-card">
              <p className="text-sm font-semibold text-white mb-1">
                Incident Trend (7 Days)
              </p>
              <p className="text-xs mb-4" style={{ color: "#475569" }}>
                Daily volume of sensitive detections and blocked transfers
              </p>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart
                  data={activity}
                  margin={{ top: 4, right: 8, left: -20, bottom: 0 }}
                >
                  <XAxis
                    dataKey="date"
                    tick={{ fill: "#334155", fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: "#334155", fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip {...tooltipStyle} />
                  <Line
                    type="monotone"
                    dataKey="scans"
                    name="Scans"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={{ fill: "#3b82f6", r: 3 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="sensitive"
                    name="Sensitive"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    dot={{ fill: "#f59e0b", r: 3 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="blocked"
                    name="Blocked"
                    stroke="#ef4444"
                    strokeWidth={2}
                    dot={{ fill: "#ef4444", r: 3 }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11, color: "#64748b" }} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Severity pie */}
            <div className="dg-card">
              <p className="text-sm font-semibold text-white mb-1">
                Incident Severity
              </p>
              <p className="text-xs mb-3" style={{ color: "#475569" }}>
                Distribution by severity level
              </p>
              {sevData.length === 0 ? (
                <div className="flex items-center justify-center h-40">
                  <p className="text-sm" style={{ color: "#475569" }}>
                    No data
                  </p>
                </div>
              ) : (
                <>
                  <ResponsiveContainer width="100%" height={160}>
                    <PieChart>
                      <Pie
                        data={sevData}
                        dataKey="value"
                        cx="50%"
                        cy="50%"
                        outerRadius={60}
                        paddingAngle={3}
                      >
                        {sevData.map((d, i) => (
                          <Cell key={i} fill={d.color} />
                        ))}
                      </Pie>
                      <Tooltip {...tooltipStyle} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="mt-2 space-y-1.5">
                    {sevData.map((d) => (
                      <div
                        key={d.name}
                        className="flex items-center justify-between text-xs"
                      >
                        <div className="flex items-center gap-2">
                          <span
                            className="w-2 h-2 rounded-full"
                            style={{ background: d.color }}
                          />
                          <span style={{ color: "#64748b" }}>{d.name}</span>
                        </div>
                        <span
                          className="font-mono"
                          style={{ color: d.color }}
                        >
                          {d.value}
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Charts row 2 */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Destination breakdown */}
            <div className="dg-card">
              <p className="text-sm font-semibold text-white mb-1">
                Exfiltration Destinations
              </p>
              <p className="text-xs mb-3" style={{ color: "#475569" }}>
                Where data was sent / attempted
              </p>
              {destData.length === 0 ? (
                <div className="flex items-center justify-center h-40">
                  <p className="text-sm" style={{ color: "#475569" }}>
                    No data
                  </p>
                </div>
              ) : (
                <>
                  <ResponsiveContainer width="100%" height={160}>
                    <PieChart>
                      <Pie
                        data={destData}
                        dataKey="value"
                        cx="50%"
                        cy="50%"
                        innerRadius={35}
                        outerRadius={60}
                        paddingAngle={4}
                      >
                        {destData.map((d, i) => (
                          <Cell key={i} fill={d.color} />
                        ))}
                      </Pie>
                      <Tooltip {...tooltipStyle} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="mt-2 space-y-1.5">
                    {destData.map((d) => (
                      <div
                        key={d.name}
                        className="flex items-center justify-between text-xs"
                      >
                        <div className="flex items-center gap-2">
                          <span
                            className="w-2 h-2 rounded-full"
                            style={{ background: d.color }}
                          />
                          <span style={{ color: "#64748b" }}>{d.name}</span>
                        </div>
                        <span
                          className="font-mono"
                          style={{ color: d.color }}
                        >
                          {d.value}
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* Classification distribution */}
            <div className="dg-card">
              <p className="text-sm font-semibold text-white mb-1">
                Data Classification
              </p>
              <p className="text-xs mb-4" style={{ color: "#475569" }}>
                Files by sensitivity label
              </p>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart
                  data={classData}
                  layout="vertical"
                  margin={{ top: 0, right: 20, left: 20, bottom: 0 }}
                >
                  <XAxis
                    type="number"
                    tick={{ fill: "#334155", fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    tick={{ fill: "#64748b", fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    width={80}
                  />
                  <Tooltip {...tooltipStyle} />
                  <Bar
                    dataKey="value"
                    name="Incidents"
                    radius={[0, 4, 4, 0]}
                  >
                    {classData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Top risky users */}
            <div className="dg-card">
              <p className="text-sm font-semibold text-white mb-1">
                Top Risky Users
              </p>
              <p className="text-xs mb-4" style={{ color: "#475569" }}>
                Users with most security incidents
              </p>
              {topUsers.length === 0 ? (
                <div className="flex items-center justify-center h-32">
                  <p className="text-sm" style={{ color: "#475569" }}>
                    No data
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {topUsers.map((u, i) => (
                    <div key={u.user} className="flex items-center gap-3">
                      <span
                        className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0"
                        style={{
                          background:
                            i === 0
                              ? "rgba(239,68,68,0.2)"
                              : "rgba(99,179,237,0.08)",
                          color: i === 0 ? "#ef4444" : "#475569",
                        }}
                      >
                        {i + 1}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span
                            className="font-mono text-xs"
                            style={{ color: "#94a3b8" }}
                          >
                            {u.user}
                          </span>
                          <span
                            className="text-[10px]"
                            style={{ color: riskColor(u.risk) }}
                          >
                            {u.incidents} incidents
                          </span>
                        </div>
                        <div
                          className="mt-1 h-1 rounded-full"
                          style={{ background: "rgba(30,58,95,0.5)" }}
                        >
                          <div
                            className="h-1 rounded-full"
                            style={{
                              width: `${u.risk}%`,
                              background: riskColor(u.risk),
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

        </div>
      )}
    </div>
  );
}
