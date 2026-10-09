"use client";

import { useEffect, useState, useCallback } from "react";
import { useAuthContext } from "@/lib/AuthContext";
import { fetchEnrollmentPolicies } from "@/lib/api";
import type { EnrollmentPolicy } from "@/lib/api";
import PolicyModal from "@/components/PolicyModal";
import { AuthError } from "@/lib/auth";

export default function EnrollmentPoliciesPage() {
  const { signalAuthFailure } = useAuthContext();

  const [policies, setPolicies] = useState<EnrollmentPolicy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [platformFilter, setPlatformFilter] = useState<string>("ALL");
  const [page, setPage] = useState(0);

  const loadPolicies = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const platform = platformFilter === "ALL" ? undefined : platformFilter;
      const data = await fetchEnrollmentPolicies(50, page * 50, platform);
      setPolicies(data);
    } catch (err) {
      if (err instanceof AuthError) {
        signalAuthFailure();
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load enrollment policies");
    } finally {
      setLoading(false);
    }
  }, [page, platformFilter, signalAuthFailure]);

  useEffect(() => {
    loadPolicies();
  }, [loadPolicies]);

  const handleModalSuccess = () => {
    setModalOpen(false);
    setPage(0);
    void loadPolicies();
  };

  const complianceLevelColor = (level: string): string => {
    switch (level) {
      case "HIGH":
        return "#ef4444";
      case "MEDIUM":
        return "#f59e0b";
      case "LOW":
        return "#10b981";
      default:
        return "#06b6d4";
    }
  };

  return (
    <div className="p-4 md:p-6">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-white mb-2">Enrollment Policies</h2>
        <p className="text-sm" style={{ color: "#94a3b8" }}>
          Create and manage device enrollment policies with DLP compliance rules
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

          <button
            onClick={() => void loadPolicies()}
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
          + Create Policy
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
            onClick={() => void loadPolicies()}
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

      {/* Policies table */}
      {!loading && policies.length === 0 && (
        <div
          className="dg-card py-12 text-center"
          style={{ border: "2px dashed rgba(99,179,237,0.2)" }}
        >
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" className="mx-auto mb-3 opacity-50">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" stroke="currentColor" strokeWidth="1.5" />
            <path d="M14 2v6h6M9 12h6M9 16h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <p className="text-sm font-semibold text-white">No enrollment policies</p>
          <p className="text-xs mt-1" style={{ color: "#475569" }}>Create a new policy to define enrollment requirements</p>
        </div>
      )}

      {!loading && policies.length > 0 && (
        <div className="dg-card p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full data-table">
              <thead>
                <tr>
                  <th>Policy Name</th>
                  <th>Platform</th>
                  <th>Organization</th>
                  <th>Compliance Level</th>
                  <th>Rules Count</th>
                  <th>Require Attestation</th>
                  <th>Created</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {policies.map((policy) => (
                  <tr key={policy.id}>
                    <td className="text-sm font-semibold text-white">{policy.name}</td>
                    <td className="text-sm">{policy.platform}</td>
                    <td className="text-xs" style={{ color: "#94a3b8" }}>
                      {policy.organization_id || "—"}
                    </td>
                    <td>
                      <span
                        className="inline-block px-2 py-1 rounded text-xs font-semibold"
                        style={{
                          background: `${complianceLevelColor(policy.compliance_level)}15`,
                          color: complianceLevelColor(policy.compliance_level),
                          border: `1px solid ${complianceLevelColor(policy.compliance_level)}30`,
                        }}
                      >
                        {policy.compliance_level}
                      </span>
                    </td>
                    <td className="text-sm">{policy.dlp_rules?.length ?? 0}</td>
                    <td className="text-sm">
                      {policy.require_attestation ? (
                        <span style={{ color: "#10b981" }}>✓ Yes</span>
                      ) : (
                        <span style={{ color: "#94a3b8" }}>— No</span>
                      )}
                    </td>
                    <td className="text-xs" style={{ color: "#94a3b8" }}>
                      {new Date(policy.created_at).toLocaleDateString()}
                    </td>
                    <td className="text-right">
                      <button
                        className="px-2 py-1 text-xs font-semibold rounded transition-colors hover:bg-blue-500/20"
                        style={{ color: "#60a5fa" }}
                      >
                        View
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
      {!loading && policies.length > 0 && (
        <div className="mt-4 flex justify-between items-center">
          <p className="text-xs" style={{ color: "#94a3b8" }}>
            Page {page + 1} • Showing {policies.length} policies
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
              disabled={policies.length < 50}
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
        <PolicyModal
          onClose={() => setModalOpen(false)}
          onSuccess={handleModalSuccess}
        />
      )}
    </div>
  );
}
