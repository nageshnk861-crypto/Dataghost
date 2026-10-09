"use client";

import { useEffect, useState, useCallback } from "react";
import { useAuthContext } from "@/lib/AuthContext";
import {
  fetchProvisioningRecords,
  revokeProvisioningRecord,
} from "@/lib/api";
import type { ProvisioningRecord } from "@/lib/api";
import ProvisioningModal from "@/components/ProvisioningModal";
import { AuthError } from "@/lib/auth";

export default function ProvisioningPage() {
  const { signalAuthFailure } = useAuthContext();

  const [records, setRecords] = useState<ProvisioningRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [platformFilter, setPlatformFilter] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [page, setPage] = useState(0);
  const [revoking, setRevoking] = useState<string | null>(null);

  const loadRecords = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const platform = platformFilter === "ALL" ? undefined : platformFilter;
      const status = statusFilter === "ALL" ? undefined : statusFilter;
      const data = await fetchProvisioningRecords(50, page * 50, platform, status);
      setRecords(data);
    } catch (err) {
      if (err instanceof AuthError) {
        signalAuthFailure();
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load provisioning records");
    } finally {
      setLoading(false);
    }
  }, [page, platformFilter, statusFilter, signalAuthFailure]);

  useEffect(() => {
    loadRecords();
  }, [loadRecords]);

  const handleRevoke = async (recordId: string) => {
    if (!confirm("Are you sure you want to revoke this provisioning record? Active enrollments using this code will fail.")) {
      return;
    }

    try {
      setRevoking(recordId);
      await revokeProvisioningRecord(recordId);
      setRecords((prev) => prev.filter((r) => r.id !== recordId));
    } catch (err) {
      if (err instanceof AuthError) {
        signalAuthFailure();
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to revoke provisioning record");
    } finally {
      setRevoking(null);
    }
  };

  const handleModalSuccess = () => {
    setModalOpen(false);
    setPage(0);
    void loadRecords();
  };

  const statusColor = (status: string): string => {
    switch (status) {
      case "ACTIVE":
        return "#10b981";
      case "REVOKED":
        return "#ef4444";
      case "EXPIRED":
        return "#f59e0b";
      default:
        return "#94a3b8";
    }
  };

  const timeUntilExpiry = (expiresAt: string): string => {
    const now = new Date();
    const expiry = new Date(expiresAt);
    const diff = expiry.getTime() - now.getTime();

    if (diff < 0) return "Expired";
    if (diff < 3600000) return "< 1 hour";
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h`;
    return `${Math.floor(diff / 86400000)}d`;
  };

  return (
    <div className="p-4 md:p-6">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-white mb-2">Device Provisioning</h2>
        <p className="text-sm" style={{ color: "#94a3b8" }}>
          Create and manage device provisioning records for zero-touch enrollment
        </p>
      </div>

      {/* Create button */}
      <div className="mb-6 flex justify-between items-center">
        <div className="flex gap-3">
          <select
            value={platformFilter}
            onChange={(e) => { setPlatformFilter(e.target.value); setPage(0); }}
            className="px-3 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer"
            style={{
              background: "rgba(26,39,68,0.5)",
              border: "1px solid rgba(99,179,237,0.1)",
              color: "#e2e8f0",
            }}
          >
            <option value="ALL">All Platforms</option>
            <option value="Windows">Windows</option>
            <option value="Android">Android</option>
            <option value="macOS">macOS</option>
            <option value="iOS">iOS</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
            className="px-3 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer"
            style={{
              background: "rgba(26,39,68,0.5)",
              border: "1px solid rgba(99,179,237,0.1)",
              color: "#e2e8f0",
            }}
          >
            <option value="ALL">All Status</option>
            <option value="ACTIVE">Active</option>
            <option value="EXPIRED">Expired</option>
            <option value="REVOKED">Revoked</option>
          </select>

          <button
            onClick={() => void loadRecords()}
            className="px-3 py-2 rounded-lg text-sm font-medium transition-colors hover:opacity-80"
            style={{
              background: "rgba(99,179,237,0.1)",
              border: "1px solid rgba(99,179,237,0.2)",
              color: "#06b6d4",
            }}
          >
            ↻ Refresh
          </button>
        </div>

        <button
          onClick={() => setModalOpen(true)}
          className="px-4 py-2 rounded-lg text-sm font-semibold transition-all hover:opacity-90"
          style={{
            background: "linear-gradient(135deg, #0891b2, #06b6d4)",
            color: "#fff",
          }}
        >
          + Create Record
        </button>
      </div>

      {/* Error state */}
      {error && (
        <div
          className="mb-4 p-4 rounded-lg flex items-center justify-between"
          style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.2)" }}
        >
          <div>
            <p className="text-sm font-semibold text-red-400">Error</p>
            <p className="text-xs mt-1" style={{ color: "#f87171" }}>{error}</p>
          </div>
          <button
            onClick={() => void loadRecords()}
            className="px-3 py-1 text-xs font-semibold rounded text-red-400 hover:bg-red-500/20 transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="dg-card h-16 animate-pulse"
              style={{ background: "rgba(26,39,68,0.4)" }}
            />
          ))}
        </div>
      )}

      {/* Records table */}
      {!loading && records.length === 0 && (
        <div
          className="dg-card py-12 text-center"
          style={{ border: "2px dashed rgba(99,179,237,0.2)" }}
        >
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" className="mx-auto mb-3 opacity-50">
            <rect x="2" y="3" width="20" height="14" rx="2" stroke="currentColor" strokeWidth="1.5" />
            <path d="M8 21h8M12 17v4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <p className="text-sm font-semibold text-white">No provisioning records</p>
          <p className="text-xs mt-1" style={{ color: "#475569" }}>Create a new provisioning record to get started</p>
        </div>
      )}

      {!loading && records.length > 0 && (
        <div className="dg-card p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full data-table">
              <thead>
                <tr>
                  <th>Record ID</th>
                  <th>Platform</th>
                  <th>Status</th>
                  <th>Device Count</th>
                  <th>Created</th>
                  <th>Expires</th>
                  <th>Last Used</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {records.map((record) => (
                  <tr key={record.id}>
                    <td className="font-mono text-xs" style={{ color: "#06b6d4" }}>{record.id?.substring(0, 8)}…</td>
                    <td className="text-sm">{record.platform}</td>
                    <td>
                      <span
                        className="inline-block px-2 py-1 rounded text-xs font-semibold"
                        style={{
                          background: `${statusColor(record.status)}15`,
                          color: statusColor(record.status),
                          border: `1px solid ${statusColor(record.status)}30`,
                        }}
                      >
                        {record.status}
                      </span>
                    </td>
                    <td className="text-sm">{record.device_count ?? 1}</td>
                    <td className="text-xs" style={{ color: "#94a3b8" }}>
                      {new Date(record.created_at).toLocaleDateString()}
                    </td>
                    <td className="text-xs">
                      <span style={{ color: timeUntilExpiry(record.expires_at) === "Expired" ? "#ef4444" : "#f59e0b" }}>
                        {timeUntilExpiry(record.expires_at)}
                      </span>
                    </td>
                    <td className="text-xs" style={{ color: "#94a3b8" }}>
                      {record.last_used_at
                        ? new Date(record.last_used_at).toLocaleDateString()
                        : "—"}
                    </td>
                    <td className="text-right">
                      <button
                        onClick={() => handleRevoke(record.id)}
                        disabled={revoking === record.id || record.status === "REVOKED"}
                        className="px-2 py-1 text-xs font-semibold rounded transition-colors hover:bg-red-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
                        style={{ color: "#ef4444" }}
                      >
                        {revoking === record.id ? "…" : "Revoke"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Pagination */}
      {!loading && records.length > 0 && (
        <div className="mt-4 flex justify-between items-center">
          <p className="text-xs" style={{ color: "#94a3b8" }}>
            Page {page + 1} • Showing {records.length} records
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="px-3 py-1 rounded text-xs font-semibold transition-colors hover:opacity-80 disabled:opacity-50"
              style={{
                background: "rgba(99,179,237,0.1)",
                border: "1px solid rgba(99,179,237,0.2)",
                color: "#06b6d4",
              }}
            >
              ← Previous
            </button>
            <button
              onClick={() => setPage(page + 1)}
              disabled={records.length < 50}
              className="px-3 py-1 rounded text-xs font-semibold transition-colors hover:opacity-80 disabled:opacity-50"
              style={{
                background: "rgba(99,179,237,0.1)",
                border: "1px solid rgba(99,179,237,0.2)",
                color: "#06b6d4",
              }}
            >
              Next →
            </button>
          </div>
        </div>
      )}

      {/* Modal */}
      {modalOpen && (
        <ProvisioningModal
          onClose={() => setModalOpen(false)}
          onSuccess={handleModalSuccess}
        />
      )}
    </div>
  );
}
