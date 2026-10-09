"use client";

import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "../../../lib/auth";
import TopBar from "../../../components/TopBar";

// ─── Types ────────────────────────────────────────────────────────────────────
interface DlpRule {
  name: string;
  display_name: string;
  category: string;
  severity: string;
  action: string;
  risk_threshold: string;
  description: string;
  enabled: boolean;
}

// ─── Colour helpers ───────────────────────────────────────────────────────────
function actionColor(a: string): string {
  if (a === "BLOCK" || a === "QUARANTINE") return "#ef4444";
  if (a === "ALERT") return "#f59e0b";
  return "#10b981";
}

function severityColor(s: string): string {
  if (s === "CRITICAL") return "#ef4444";
  if (s === "HIGH")     return "#f59e0b";
  if (s === "MEDIUM")   return "#60a5fa";
  return "#10b981";
}

function categoryColor(c: string): string {
  if (c === "PII")         return "#a78bfa";
  if (c === "FINANCIAL")   return "#f59e0b";
  if (c === "CREDENTIALS") return "#ef4444";
  if (c === "CORPORATE")   return "#06b6d4";
  return "#64748b";
}

// ─── Skeleton row ─────────────────────────────────────────────────────────────
function SkeletonRow() {
  return (
    <div
      className="dg-card flex items-center gap-4 animate-pulse"
      style={{ opacity: 0.5 }}
    >
      <div className="w-2 h-10 rounded-full" style={{ background: "rgba(26,39,68,0.8)" }} />
      <div className="flex-1 space-y-2">
        <div className="h-3 w-40 rounded" style={{ background: "rgba(26,39,68,0.8)" }} />
        <div className="h-2 w-64 rounded" style={{ background: "rgba(26,39,68,0.8)" }} />
      </div>
      <div className="h-5 w-16 rounded" style={{ background: "rgba(26,39,68,0.8)" }} />
      <div className="h-5 w-14 rounded" style={{ background: "rgba(26,39,68,0.8)" }} />
    </div>
  );
}

// ─── Category grouping order ──────────────────────────────────────────────────
const CATEGORY_ORDER = ["CREDENTIALS", "PII", "FINANCIAL", "CORPORATE"];

// ─── Main ─────────────────────────────────────────────────────────────────────
export default function PoliciesPage() {
  const [rules, setRules]       = useState<DlpRule[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState("");
  const [selected, setSelected] = useState<DlpRule | null>(null);
  const [catFilter, setCatFilter] = useState("ALL");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/api/dlp-rules");
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.detail ?? `HTTP ${res.status}`);
      }
      const data: DlpRule[] = await res.json();
      setRules(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load DLP rules");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Filter by category
  const categories = ["ALL", ...CATEGORY_ORDER];
  const filtered = catFilter === "ALL"
    ? rules
    : rules.filter((r) => r.category === catFilter);

  // Group filtered rules by category in defined order
  const grouped = CATEGORY_ORDER.reduce<Record<string, DlpRule[]>>((acc, cat) => {
    const inCat = filtered.filter((r) => r.category === cat);
    if (inCat.length > 0) acc[cat] = inCat;
    return acc;
  }, {});

  const criticalCount  = rules.filter((r) => r.severity === "CRITICAL").length;
  const blockCount     = rules.filter((r) => r.action === "BLOCK").length;
  const alertCount     = rules.filter((r) => r.action === "ALERT").length;

  return (
    <div className="min-h-screen">
      <TopBar
        title="DLP Policies"
        subtitle="Active detection rules enforced by the DataGhost scan engine"
      >
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

        {/* Policy engine banner */}
        <div
          className="dg-card"
          style={{
            background: "rgba(124,58,237,0.04)",
            border: "1px solid rgba(124,58,237,0.12)",
          }}
        >
          <div className="flex items-center gap-3">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
              style={{ background: "rgba(124,58,237,0.15)" }}
            >
              <span className="text-lg">🛡</span>
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold" style={{ color: "#a78bfa" }}>
                DataGhost DLP Engine
              </p>
              <p className="text-xs mt-0.5" style={{ color: "#475569" }}>
                Rules are evaluated on every file scan. All rules are always active.
                Actions: ALERT (log + notify) · BLOCK (prevent transfer).
              </p>
            </div>
            <div className="text-right flex-shrink-0">
              <p className="text-2xl font-bold" style={{ color: "#a78bfa" }}>
                {loading ? "—" : rules.length}
              </p>
              <p className="text-[11px]" style={{ color: "#475569" }}>Active rules</p>
            </div>
          </div>
        </div>

        {/* Summary stat cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: "Total Rules",     value: rules.length,   color: "#94a3b8" },
            { label: "BLOCK Actions",   value: blockCount,     color: "#ef4444" },
            { label: "ALERT Actions",   value: alertCount,     color: "#f59e0b" },
            { label: "Critical Rules",  value: criticalCount,  color: "#ef4444" },
          ].map((s) => (
            <div key={s.label} className="stat-card">
              <p className="text-[11px] uppercase tracking-wide" style={{ color: "#475569" }}>
                {s.label}
              </p>
              <p className="text-2xl font-bold mt-1" style={{ color: s.color }}>
                {loading ? "—" : s.value}
              </p>
            </div>
          ))}
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
            <button className="btn-ghost text-xs ml-4" onClick={load}>
              Retry
            </button>
          </div>
        )}

        {/* Category filter tabs */}
        {!loading && !error && (
          <div className="flex flex-wrap gap-2">
            {categories.map((cat) => {
              const active = catFilter === cat;
              const color = cat === "ALL" ? "#94a3b8" : categoryColor(cat);
              return (
                <button
                  key={cat}
                  onClick={() => { setCatFilter(cat); setSelected(null); }}
                  className="text-xs px-3 py-1.5 rounded-lg font-semibold transition-all"
                  style={{
                    background: active ? `${color}20` : "transparent",
                    border: `1px solid ${active ? color : "rgba(99,179,237,0.1)"}`,
                    color: active ? color : "#475569",
                    cursor: "pointer",
                  }}
                >
                  {cat === "ALL"
                    ? `All (${rules.length})`
                    : `${cat} (${rules.filter((r) => r.category === cat).length})`}
                </button>
              );
            })}
          </div>
        )}

        {/* Main layout: rule list + detail panel */}
        <div className="flex gap-5">
          <div className="flex-1 min-w-0 space-y-6">
            {loading ? (
              Array.from({ length: 6 }).map((_, i) => <SkeletonRow key={i} />)
            ) : Object.keys(grouped).length === 0 ? (
              <div
                className="flex flex-col items-center justify-center py-16"
                style={{ color: "#1e3a5f" }}
              >
                <span className="text-4xl mb-3">🛡</span>
                <p className="text-sm">No rules match this filter</p>
              </div>
            ) : (
              Object.entries(grouped).map(([cat, catRules]) => (
                <div key={cat}>
                  {/* Category header */}
                  <div className="flex items-center gap-2 mb-3">
                    <span
                      className="text-[11px] font-bold px-2.5 py-1 rounded-full"
                      style={{
                        background: `${categoryColor(cat)}15`,
                        color: categoryColor(cat),
                        border: `1px solid ${categoryColor(cat)}30`,
                      }}
                    >
                      {cat}
                    </span>
                    <div
                      className="flex-1 h-px"
                      style={{ background: "rgba(99,179,237,0.06)" }}
                    />
                    <span className="text-[11px]" style={{ color: "#1e3a5f" }}>
                      {catRules.length} rule{catRules.length !== 1 ? "s" : ""}
                    </span>
                  </div>

                  {/* Rules in category */}
                  <div className="space-y-2">
                    {catRules.map((rule) => {
                      const isSelected = selected?.name === rule.name;
                      return (
                        <div
                          key={rule.name}
                          className="dg-card glass-hover cursor-pointer flex items-center gap-4"
                          style={
                            isSelected
                              ? { borderColor: `${categoryColor(rule.category)}35` }
                              : {}
                          }
                          onClick={() =>
                            setSelected(isSelected ? null : rule)
                          }
                        >
                          {/* Severity stripe */}
                          <div
                            className="w-1.5 h-10 rounded-full flex-shrink-0"
                            style={{ background: severityColor(rule.severity) }}
                          />

                          {/* Rule info */}
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-semibold text-white">
                              {rule.display_name}
                            </p>
                            <p
                              className="text-[11px] mt-0.5 truncate"
                              style={{ color: "#334155" }}
                            >
                              {rule.description}
                            </p>
                          </div>

                          {/* Tags */}
                          <div className="flex items-center gap-2 flex-shrink-0">
                            <span
                              className="text-[10px] px-2 py-0.5 rounded font-semibold"
                              style={{
                                background: `${severityColor(rule.severity)}15`,
                                color: severityColor(rule.severity),
                                border: `1px solid ${severityColor(rule.severity)}30`,
                              }}
                            >
                              {rule.severity}
                            </span>
                            <span
                              className="text-[10px] px-2 py-0.5 rounded font-bold"
                              style={{
                                background: `${actionColor(rule.action)}15`,
                                color: actionColor(rule.action),
                                border: `1px solid ${actionColor(rule.action)}30`,
                              }}
                            >
                              {rule.action}
                            </span>
                            <span
                              className="text-[10px] font-mono"
                              style={{ color: "#334155" }}
                            >
                              {rule.risk_threshold}
                            </span>
                            {/* Always-on indicator */}
                            <div className="flex items-center gap-1 ml-1">
                              <span
                                className="w-1.5 h-1.5 rounded-full"
                                style={{
                                  background: "#10b981",
                                  boxShadow: "0 0 4px #10b981",
                                }}
                              />
                              <span
                                className="text-[10px] font-semibold"
                                style={{ color: "#10b981" }}
                              >
                                ON
                              </span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Detail panel */}
          {selected && (
            <div
              className="w-72 flex-shrink-0 dg-card self-start"
              style={{ border: `1px solid ${categoryColor(selected.category)}25` }}
            >
              <div className="flex items-center justify-between mb-4">
                <p className="text-sm font-semibold text-white">Rule Detail</p>
                <button
                  onClick={() => setSelected(null)}
                  style={{
                    color: "#475569",
                    cursor: "pointer",
                    background: "none",
                    border: "none",
                    fontFamily: "inherit",
                    fontSize: "12px",
                  }}
                >
                  ✕
                </button>
              </div>

              <div className="space-y-3 text-xs">
                {[
                  { label: "NAME",           value: selected.display_name },
                  { label: "CATEGORY",       value: selected.category },
                  { label: "SEVERITY",       value: selected.severity },
                  { label: "ACTION",         value: selected.action },
                  { label: "RISK THRESHOLD", value: selected.risk_threshold },
                  { label: "STATUS",         value: "ALWAYS ACTIVE" },
                ].map((row) => (
                  <div key={row.label}>
                    <p
                      style={{
                        color: "#334155",
                        fontSize: "10px",
                        letterSpacing: "0.05em",
                      }}
                    >
                      {row.label}
                    </p>
                    <p
                      className="mt-0.5 font-medium"
                      style={{
                        color:
                          row.label === "ACTION"
                            ? actionColor(selected.action)
                            : row.label === "SEVERITY"
                            ? severityColor(selected.severity)
                            : row.label === "CATEGORY"
                            ? categoryColor(selected.category)
                            : row.label === "STATUS"
                            ? "#10b981"
                            : "#94a3b8",
                      }}
                    >
                      {row.value}
                    </p>
                  </div>
                ))}

                <div
                  className="pt-2 border-t"
                  style={{ borderColor: "rgba(99,179,237,0.06)" }}
                >
                  <p
                    style={{
                      color: "#334155",
                      fontSize: "10px",
                      letterSpacing: "0.05em",
                    }}
                  >
                    DESCRIPTION
                  </p>
                  <p
                    className="mt-1 leading-relaxed"
                    style={{ color: "#64748b" }}
                  >
                    {selected.description}
                  </p>
                </div>

                <div
                  className="pt-2 border-t"
                  style={{ borderColor: "rgba(99,179,237,0.06)" }}
                >
                  <p
                    className="text-[10px]"
                    style={{ color: "#1e3a5f" }}
                  >
                    Rules are enforced by the backend scan engine and cannot be disabled from the UI in this version.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer note */}
        {!loading && !error && (
          <p className="text-[11px] text-center" style={{ color: "#1e3a5f" }}>
            {rules.length} rules · sourced live from backend DLP engine ·
            all rules always active
          </p>
        )}
      </div>
    </div>
  );
}
