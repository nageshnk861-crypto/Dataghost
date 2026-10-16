"use client";

import { useEffect, useState, useCallback } from "react";
import TopBar from "@/components/TopBar";
import {
  fetchFindings,
  fetchFindingStats,
  patchFindingStatus,
} from "@/lib/api";
import type { FindingRow, FindingStats } from "@/lib/api";

const SEVERITY_OPTIONS = ["ALL", "LOW", "MEDIUM", "HIGH", "CRITICAL"] as const;
const STATUS_OPTIONS = ["ALL", "OPEN", "ACKNOWLEDGED", "RESOLVED", "FALSE_POSITIVE"] as const;
const CATEGORY_OPTIONS = ["ALL", "CREDENTIALS", "PII", "FINANCIAL", "CORPORATE"] as const;

function severityColor(s: string) {
  const norm = s?.toUpperCase();
  if (norm === "CRITICAL") return "#ef4444";
  if (norm === "HIGH") return "#f59e0b";
  if (norm === "MEDIUM") return "#3b82f6";
  return "#10b981";
}

function statusColor(s: string) {
  const norm = s?.toUpperCase();
  if (norm === "OPEN") return "#ef4444";
  if (norm === "ACKNOWLEDGED") return "#f59e0b";
  if (norm === "RESOLVED") return "#10b981";
  return "#6b7280";
}

export default function FindingsPage() {
  const [findings, setFindings] = useState<FindingRow[]>([]);
  const [stats, setStats] = useState<FindingStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFinding, setSelectedFinding] = useState<FindingRow | null>(null);

  // Filters and pagination
  const [page, setPage] = useState(1);
  const [pageSize] = useState(15);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [severity, setSeverity] = useState<string>("ALL");
  const [status, setStatus] = useState<string>("ALL");
  const [category, setCategory] = useState<string>("ALL");
  const [search, setSearch] = useState<string>("");
  const [updatingId, setUpdatingId] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [listRes, statsRes] = await Promise.all([
        fetchFindings({
          page,
          per_page: pageSize,
          severity: severity !== "ALL" ? severity : undefined,
          status: status !== "ALL" ? status : undefined,
          category: category !== "ALL" ? category : undefined,
          search: search.trim() ? search.trim() : undefined,
        }),
        fetchFindingStats(),
      ]);
      setFindings(listRes.items || []);
      setTotal(listRes.total || 0);
      setTotalPages(listRes.pages || 1);
      setStats(statsRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load DLP findings.");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, severity, status, category, search]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleStatusChange = async (findingId: number, newStatus: string) => {
    setUpdatingId(findingId);
    try {
      await patchFindingStatus(findingId, newStatus);
      // Refresh list and stats
      await loadData();
      if (selectedFinding && selectedFinding.id === findingId) {
        setSelectedFinding((prev) => (prev ? { ...prev, status: newStatus } : null));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Status update failed.");
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <div className="min-h-screen pb-12" style={{ background: "#0a0f1e" }}>
      <TopBar title="DLP Findings" subtitle="Persisted secret & sensitive data discoveries">
        <button
          onClick={() => loadData()}
          disabled={loading}
          className="px-3 py-1.5 rounded-lg text-xs font-medium text-cyan-300 transition-colors flex items-center gap-1.5 cursor-pointer"
          style={{ background: "rgba(6, 182, 212, 0.12)", border: "1px solid rgba(6, 182, 212, 0.25)" }}
        >
          <svg className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} fill="none" viewBox="0 0 24 24">
            <path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Refresh
        </button>
      </TopBar>

      <div className="max-w-7xl mx-auto px-4 md:px-6 pt-6 space-y-6">
        {/* KPI Summary Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <div
            className="p-4 rounded-xl border backdrop-blur-md"
            style={{ background: "rgba(14, 23, 42, 0.7)", borderColor: "rgba(255,255,255,0.06)" }}
          >
            <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Total Findings</div>
            <div className="text-2xl font-bold text-white mt-1">{stats?.total ?? "–"}</div>
          </div>
          <div
            className="p-4 rounded-xl border backdrop-blur-md"
            style={{ background: "rgba(14, 23, 42, 0.7)", borderColor: "rgba(239, 68, 68, 0.2)" }}
          >
            <div className="text-[11px] font-medium uppercase tracking-wider text-red-400">Open Issues</div>
            <div className="text-2xl font-bold text-red-400 mt-1">{stats?.open ?? "–"}</div>
          </div>
          <div
            className="p-4 rounded-xl border backdrop-blur-md"
            style={{ background: "rgba(14, 23, 42, 0.7)", borderColor: "rgba(245, 158, 11, 0.2)" }}
          >
            <div className="text-[11px] font-medium uppercase tracking-wider text-amber-400">Acknowledged</div>
            <div className="text-2xl font-bold text-amber-400 mt-1">{stats?.acknowledged ?? "–"}</div>
          </div>
          <div
            className="p-4 rounded-xl border backdrop-blur-md"
            style={{ background: "rgba(14, 23, 42, 0.7)", borderColor: "rgba(16, 185, 129, 0.2)" }}
          >
            <div className="text-[11px] font-medium uppercase tracking-wider text-emerald-400">Resolved</div>
            <div className="text-2xl font-bold text-emerald-400 mt-1">{stats?.resolved ?? "–"}</div>
          </div>
          <div
            className="p-4 rounded-xl border backdrop-blur-md"
            style={{ background: "rgba(14, 23, 42, 0.7)", borderColor: "rgba(255,255,255,0.06)" }}
          >
            <div className="text-[11px] font-medium uppercase tracking-wider text-slate-400">False Positive</div>
            <div className="text-2xl font-bold text-slate-400 mt-1">{stats?.false_positive ?? "–"}</div>
          </div>
        </div>

        {/* Filter Toolbar */}
        <div
          className="p-4 rounded-xl border backdrop-blur-md flex flex-wrap items-center gap-3"
          style={{ background: "rgba(14, 23, 42, 0.6)", borderColor: "rgba(255, 255, 255, 0.08)" }}
        >
          {/* Search */}
          <div className="flex-1 min-w-[200px] relative">
            <input
              type="text"
              placeholder="Search by file name, rule, or description…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-full pl-9 pr-3 py-2 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
              style={{ background: "rgba(30, 41, 59, 0.6)", border: "1px solid rgba(255, 255, 255, 0.1)" }}
            />
            <svg
              className="w-4 h-4 text-slate-400 absolute left-3 top-2.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>

          {/* Severity */}
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Severity:</span>
            <select
              value={severity}
              onChange={(e) => {
                setSeverity(e.target.value);
                setPage(1);
              }}
              className="px-2.5 py-1.5 rounded-lg text-xs text-white font-medium focus:outline-none"
              style={{ background: "rgba(30, 41, 59, 0.8)", border: "1px solid rgba(255, 255, 255, 0.1)" }}
            >
              {SEVERITY_OPTIONS.map((opt) => (
                <option key={opt} value={opt} className="bg-slate-900 text-white">
                  {opt}
                </option>
              ))}
            </select>
          </div>

          {/* Status */}
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Status:</span>
            <select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
              className="px-2.5 py-1.5 rounded-lg text-xs text-white font-medium focus:outline-none"
              style={{ background: "rgba(30, 41, 59, 0.8)", border: "1px solid rgba(255, 255, 255, 0.1)" }}
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt} value={opt} className="bg-slate-900 text-white">
                  {opt}
                </option>
              ))}
            </select>
          </div>

          {/* Category */}
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">Category:</span>
            <select
              value={category}
              onChange={(e) => {
                setCategory(e.target.value);
                setPage(1);
              }}
              className="px-2.5 py-1.5 rounded-lg text-xs text-white font-medium focus:outline-none"
              style={{ background: "rgba(30, 41, 59, 0.8)", border: "1px solid rgba(255, 255, 255, 0.1)" }}
            >
              {CATEGORY_OPTIONS.map((opt) => (
                <option key={opt} value={opt} className="bg-slate-900 text-white">
                  {opt}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="p-3 rounded-lg text-xs text-red-300 bg-red-950/40 border border-red-500/20">
            {error}
          </div>
        )}

        {/* Findings Table */}
        <div
          className="rounded-xl border overflow-hidden backdrop-blur-md"
          style={{ background: "rgba(14, 23, 42, 0.7)", borderColor: "rgba(255, 255, 255, 0.08)" }}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b" style={{ borderColor: "rgba(255, 255, 255, 0.08)", background: "rgba(15, 23, 42, 0.5)" }}>
                  <th className="py-3 px-4 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Severity</th>
                  <th className="py-3 px-4 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Rule & Category</th>
                  <th className="py-3 px-4 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">File & Evidence</th>
                  <th className="py-3 px-4 text-[11px] font-semibold text-slate-400 uppercase tracking-wider text-center">Hits</th>
                  <th className="py-3 px-4 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Status</th>
                  <th className="py-3 px-4 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Last Seen</th>
                  <th className="py-3 px-4 text-[11px] font-semibold text-slate-400 uppercase tracking-wider text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {loading ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-slate-400 text-xs">
                      <div className="flex items-center justify-center gap-2">
                        <svg className="w-4 h-4 animate-spin text-cyan-400" viewBox="0 0 24 24" fill="none">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                        </svg>
                        Loading findings…
                      </div>
                    </td>
                  </tr>
                ) : findings.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-slate-400 text-xs">
                      No findings found matching the criteria.
                    </td>
                  </tr>
                ) : (
                  findings.map((f) => {
                    const sevCol = severityColor(f.severity);
                    const stCol = statusColor(f.status);
                    return (
                      <tr
                        key={f.id}
                        onClick={() => setSelectedFinding(f)}
                        className="hover:bg-slate-800/40 transition-colors cursor-pointer"
                      >
                        {/* Severity */}
                        <td className="py-3.5 px-4 whitespace-nowrap">
                          <span
                            className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold"
                            style={{
                              color: sevCol,
                              background: `${sevCol}18`,
                              border: `1px solid ${sevCol}40`,
                            }}
                          >
                            <span className="w-1.5 h-1.5 rounded-full" style={{ background: sevCol }} />
                            {f.severity}
                          </span>
                        </td>

                        {/* Rule & Category */}
                        <td className="py-3.5 px-4">
                          <div className="font-semibold text-xs text-white">{f.rule_id || "Unknown Rule"}</div>
                          <div className="text-[11px] text-slate-400 flex items-center gap-1.5 mt-0.5">
                            <span className="px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 font-mono text-[10px]">
                              {f.category || "GENERAL"}
                            </span>
                          </div>
                        </td>

                        {/* File & Evidence */}
                        <td className="py-3.5 px-4 max-w-xs">
                          <div className="text-xs font-medium text-slate-200 truncate">{f.file_name || "Unknown file"}</div>
                          <div
                            className="mt-1 px-2 py-1 rounded font-mono text-[11px] text-cyan-300 truncate"
                            style={{ background: "rgba(6, 182, 212, 0.08)", border: "1px solid rgba(6, 182, 212, 0.15)" }}
                          >
                            {f.evidence_redacted || "No evidence recorded"}
                          </div>
                        </td>

                        {/* Hits (Occurrence count) */}
                        <td className="py-3.5 px-4 text-center">
                          <span className="inline-block px-2 py-0.5 rounded-full text-[11px] font-mono text-slate-300 bg-slate-800/80 border border-slate-700">
                            {f.occurrence_count || 1}
                          </span>
                        </td>

                        {/* Status */}
                        <td className="py-3.5 px-4 whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                          <select
                            value={f.status}
                            disabled={updatingId === f.id}
                            onChange={(e) => handleStatusChange(f.id, e.target.value)}
                            className="text-xs font-semibold rounded-lg px-2 py-1 focus:outline-none cursor-pointer"
                            style={{
                              color: stCol,
                              background: `${stCol}15`,
                              border: `1px solid ${stCol}40`,
                            }}
                          >
                            <option value="OPEN" className="bg-slate-900 text-red-400">OPEN</option>
                            <option value="ACKNOWLEDGED" className="bg-slate-900 text-amber-400">ACKNOWLEDGED</option>
                            <option value="RESOLVED" className="bg-slate-900 text-emerald-400">RESOLVED</option>
                            <option value="FALSE_POSITIVE" className="bg-slate-900 text-slate-400">FALSE_POSITIVE</option>
                          </select>
                        </td>

                        {/* Last Seen */}
                        <td className="py-3.5 px-4 whitespace-nowrap text-xs text-slate-400 font-mono">
                          {f.last_seen_at ? new Date(f.last_seen_at).toLocaleDateString() : "–"}
                        </td>

                        {/* Actions */}
                        <td className="py-3.5 px-4 whitespace-nowrap text-right" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => setSelectedFinding(f)}
                            className="px-2.5 py-1 text-xs rounded-lg text-slate-300 hover:text-white bg-slate-800/80 hover:bg-slate-700/80 transition-colors"
                          >
                            Details
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination Toolbar */}
          <div
            className="flex items-center justify-between px-4 py-3 border-t text-xs text-slate-400"
            style={{ borderColor: "rgba(255, 255, 255, 0.08)" }}
          >
            <div>
              Showing {findings.length > 0 ? (page - 1) * pageSize + 1 : 0} to{" "}
              {Math.min(page * pageSize, total)} of {total} findings
            </div>
            <div className="flex items-center gap-2">
              <button
                disabled={page <= 1 || loading}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-3 py-1 rounded-lg border border-slate-700 disabled:opacity-40 hover:bg-slate-800 transition-colors"
              >
                Previous
              </button>
              <span className="font-mono text-slate-300">
                {page} / {totalPages || 1}
              </span>
              <button
                disabled={page >= totalPages || loading}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="px-3 py-1 rounded-lg border border-slate-700 disabled:opacity-40 hover:bg-slate-800 transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Details Drawer / Modal */}
      {selectedFinding && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 backdrop-blur-sm"
          style={{ background: "rgba(3, 7, 18, 0.75)" }}
          onClick={() => setSelectedFinding(null)}
        >
          <div
            className="w-full max-w-xl rounded-2xl border p-6 space-y-4 shadow-2xl"
            style={{ background: "#0e1726", borderColor: "rgba(6, 182, 212, 0.2)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between border-b pb-3" style={{ borderColor: "rgba(255,255,255,0.08)" }}>
              <div>
                <div className="text-xs font-semibold text-cyan-400 uppercase tracking-wider">
                  Finding #{selectedFinding.id}
                </div>
                <h3 className="text-base font-bold text-white mt-0.5">{selectedFinding.rule_id}</h3>
              </div>
              <button
                onClick={() => setSelectedFinding(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-slate-400 text-[11px] block">Severity</span>
                  <span className="font-bold text-sm" style={{ color: severityColor(selectedFinding.severity) }}>
                    {selectedFinding.severity}
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800">
                  <span className="text-slate-400 text-[11px] block">Status</span>
                  <span className="font-bold text-sm" style={{ color: statusColor(selectedFinding.status) }}>
                    {selectedFinding.status}
                  </span>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 space-y-2">
                <div className="flex justify-between">
                  <span className="text-slate-400">File:</span>
                  <span className="font-mono text-white">{selectedFinding.file_name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Fingerprint:</span>
                  <span className="font-mono text-slate-300">{selectedFinding.fingerprint || "–"}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Occurrences:</span>
                  <span className="font-mono text-slate-300">{selectedFinding.occurrence_count}</span>
                </div>
                {selectedFinding.device_id && (
                  <div className="flex justify-between">
                    <span className="text-slate-400">Device ID:</span>
                    <span className="font-mono text-slate-300">{selectedFinding.device_id}</span>
                  </div>
                )}
              </div>

              <div>
                <label className="text-slate-400 text-[11px] uppercase font-bold tracking-wider block mb-1">
                  Redacted Evidence (Non-Plaintext)
                </label>
                <pre
                  className="p-3 rounded-lg font-mono text-[11px] text-cyan-300 overflow-x-auto whitespace-pre-wrap break-all"
                  style={{ background: "rgba(6, 182, 212, 0.06)", border: "1px solid rgba(6, 182, 212, 0.2)" }}
                >
                  {selectedFinding.evidence_redacted}
                </pre>
              </div>

              {selectedFinding.description && (
                <div>
                  <label className="text-slate-400 text-[11px] uppercase font-bold tracking-wider block mb-1">
                    Description
                  </label>
                  <p className="text-slate-300 leading-relaxed">{selectedFinding.description}</p>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t" style={{ borderColor: "rgba(255,255,255,0.08)" }}>
              <button
                onClick={() => setSelectedFinding(null)}
                className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
