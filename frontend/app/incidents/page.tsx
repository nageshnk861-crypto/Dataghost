"use client";

import { useEffect, useState, useCallback } from "react";
import Sidebar, { toggleSidebar } from "../../components/Sidebar";
import IncidentTable from "../../components/IncidentTable";
import type { IncidentRow } from "../../components/IncidentTable";
import { fetchIncidents, patchIncidentStatus } from "@/lib/api";
import { useAuthGuard } from "@/lib/useAuthGuard";

const SEVERITY_OPTIONS = ["ALL", "LOW", "MEDIUM", "HIGH", "CRITICAL"] as const;
const STATUS_OPTIONS = ["ALL", "OPEN", "ACKNOWLEDGED", "RESOLVED"] as const;
const PAGE_SIZE = 10;

export default function IncidentsPage() {
  const checked = useAuthGuard();

  const [incidents, setIncidents] = useState<IncidentRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [severity, setSeverity] = useState("ALL");
  const [status, setStatus] = useState("ALL");
  const [search, setSearch] = useState("");

  const loadIncidents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchIncidents({
        page,
        per_page: PAGE_SIZE,
        severity: severity !== "ALL" ? severity : undefined,
        status: status !== "ALL" ? status : undefined,
      });
      setIncidents(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load incidents");
    } finally {
      setLoading(false);
    }
  }, [page, severity, status]);

  useEffect(() => {
    if (checked) loadIncidents();
  }, [checked, loadIncidents]);

  async function handleStatusChange(incidentId: string, newStatus: string) {
    try {
      await patchIncidentStatus(incidentId, newStatus);
      await loadIncidents();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Status update failed");
    }
  }

  // Client-side search over current page
  const filtered = incidents.filter((inc) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      inc.filename?.toLowerCase().includes(q) ||
      inc.user?.toLowerCase().includes(q) ||
      inc.incident_id?.toLowerCase().includes(q) ||
      inc.classification?.toLowerCase().includes(q)
    );
  });

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const criticalCount = incidents.filter((i) => i.severity === "CRITICAL").length;
  const blockedCount = incidents.filter((i) => i.action_taken === "BLOCKED").length;

  if (!checked) {
    return (
      <div className="flex items-center justify-center min-h-screen" style={{ background: "#0a0f1e" }}>
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen" style={{ background: "#0a0f1e" }}>
      <Sidebar />
      <main className="flex-1 min-h-screen overflow-y-auto md:ml-64">
        {/* Header */}
        <div
          className="sticky top-0 z-30 flex items-center justify-between px-6 py-4"
          style={{
            background: "rgba(10,15,30,0.9)",
            backdropFilter: "blur(12px)",
            borderBottom: "1px solid #1a2744",
          }}
        >
          <div className="flex items-center gap-3">
            {/* Hamburger — mobile only */}
            <button
              type="button"
              onClick={toggleSidebar}
              aria-label="Open navigation menu"
              className="md:hidden flex items-center justify-center w-8 h-8 rounded-lg transition-colors"
              style={{ color: "#94a3b8", background: "rgba(26,39,68,0.5)", border: "1px solid #1a2744" }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
              </svg>
            </button>
            <h1 className="text-lg font-bold text-white">Incidents</h1>
            <span
              className="px-2.5 py-1 rounded-full text-xs font-bold"
              style={{
                background: "rgba(255,59,59,0.1)",
                color: "#ff3b3b",
                border: "1px solid rgba(255,59,59,0.2)",
              }}
            >
              {total} total
            </span>
          </div>
        </div>

        <div className="p-6 animate-fade-up space-y-5">
          {/* Error banner */}
          {error && (
            <div
              className="px-4 py-3 rounded-lg text-sm flex items-center justify-between"
              style={{
                background: "rgba(255,59,59,0.06)",
                border: "1px solid rgba(255,59,59,0.2)",
                color: "#ff3b3b",
              }}
            >
              <span>⚠ {error}</span>
              <button
                className="btn-ghost text-xs"
                onClick={loadIncidents}
              >
                Retry
              </button>
            </div>
          )}

          {/* Stats row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: "Total Incidents", value: total, color: "#94a3b8" },
              { label: "Critical", value: criticalCount, color: "#ff3b3b" },
              { label: "Blocked", value: blockedCount, color: "#ff9f0a" },
              { label: "This Page", value: filtered.length, color: "#00d4ff" },
            ].map((s) => (
              <div
                key={s.label}
                className="text-center rounded-xl py-3 px-4"
                style={{ background: "#0f1729", border: "1px solid #1a2744" }}
              >
                <p className="text-2xl font-bold" style={{ color: s.color }}>
                  {s.value}
                </p>
                <p className="text-xs mt-0.5" style={{ color: "#475569" }}>
                  {s.label}
                </p>
              </div>
            ))}
          </div>

          {/* Filter bar */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Severity filter */}
            <select
              value={severity}
              onChange={(e) => {
                setSeverity(e.target.value);
                setPage(1);
              }}
              className="dg-select"
            >
              {SEVERITY_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {s === "ALL" ? "All Severities" : s}
                </option>
              ))}
            </select>

            {/* Status filter */}
            <select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
              className="dg-select"
            >
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {s === "ALL" ? "All Statuses" : s}
                </option>
              ))}
            </select>

            {/* Search */}
            <div className="relative flex-1 min-w-[200px]">
              <svg
                className="absolute left-3 top-1/2 -translate-y-1/2"
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                style={{ color: "#475569" }}
              >
                <circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="1.5" />
                <path d="M21 21l-4.35-4.35" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              <input
                type="text"
                className="dg-input pl-9"
                placeholder="Search by file, user, or incident ID…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>

          {/* Table */}
          <div
            className="rounded-xl overflow-hidden"
            style={{ background: "#0f1729", border: "1px solid #1a2744" }}
          >
            <IncidentTable
              incidents={filtered}
              loading={loading}
              onStatusChange={handleStatusChange}
            />

            {/* Pagination */}
            {!loading && totalPages > 1 && (
              <div
                className="flex items-center justify-between px-5 py-3 border-t"
                style={{ borderColor: "#1a2744" }}
              >
                <button
                  className="btn-ghost text-xs"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  style={{ opacity: page === 1 ? 0.4 : 1 }}
                >
                  ← Previous
                </button>
                <span className="text-xs" style={{ color: "#475569" }}>
                  Page {page} of {totalPages}
                </span>
                <button
                  className="btn-ghost text-xs"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  style={{ opacity: page === totalPages ? 0.4 : 1 }}
                >
                  Next →
                </button>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
