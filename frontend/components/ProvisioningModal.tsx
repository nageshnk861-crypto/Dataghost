"use client";

import { useState, useRef, useEffect } from "react";
import { createProvisioningRecord } from "@/lib/api";
import type { EnrollmentCreateResponse } from "@/lib/api";

interface Props {
  onClose: () => void;
  onSuccess: () => void;
}

export default function ProvisioningModal({ onClose, onSuccess }: Props) {
  const [platform, setPlatform] = useState("Windows");
  const [deviceCount, setDeviceCount] = useState(1);
  const [expirationDays, setExpirationDays] = useState(7);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EnrollmentCreateResponse | null>(null);
  const [copied, setCopied] = useState(false);

  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) {
        clearTimeout(copyTimeoutRef.current);
      }
    };
  }, []);

  const handleCreate = async () => {
    if (loading) return;

    try {
      setLoading(true);
      setError(null);
      
      // Note: In a real implementation, organizationId would be fetched from context
      // For now we use a placeholder that the backend will handle
      const response = await createProvisioningRecord(
        platform,
        "default-org",
        deviceCount,
        expirationDays
      );
      
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create provisioning record");
    } finally {
      setLoading(false);
    }
  };

  const handleCopyCode = async () => {
    if (!result?.enrollment_code) return;

    try {
      await navigator.clipboard.writeText(result.enrollment_code);
      setCopied(true);
      
      if (copyTimeoutRef.current) {
        clearTimeout(copyTimeoutRef.current);
      }
      copyTimeoutRef.current = setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  const handleSuccess = () => {
    onSuccess();
    onClose();
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 flex items-center justify-center"
        style={{ background: "rgba(3,7,18,0.7)", backdropFilter: "blur(4px)" }}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div
        className="fixed top-1/2 left-1/2 z-50 w-full max-w-lg rounded-xl shadow-2xl overflow-hidden transform -translate-x-1/2 -translate-y-1/2"
        style={{
          background: "#0d1526",
          border: "1px solid rgba(99,179,237,0.1)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="px-6 py-4 border-b flex items-center justify-between"
          style={{ borderColor: "rgba(99,179,237,0.1)" }}
        >
          <div>
            <h2 className="text-lg font-semibold text-white">Create Provisioning Record</h2>
            <p className="text-xs mt-1" style={{ color: "#94a3b8" }}>
              Generate enrollment codes for zero-touch device provisioning
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/50 transition-colors"
            aria-label="Close"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-4 max-h-96 overflow-y-auto">
          {!result ? (
            <div className="space-y-4">
              {error && (
                <div
                  className="p-3 rounded-lg"
                  style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.2)" }}
                >
                  <p className="text-xs font-semibold text-red-400">Error</p>
                  <p className="text-xs mt-1" style={{ color: "#f87171" }}>{error}</p>
                </div>
              )}

              {/* Platform */}
              <div>
                <label className="block text-xs font-semibold mb-2" style={{ color: "#94a3b8" }}>
                  PLATFORM
                </label>
                <select
                  value={platform}
                  onChange={(e) => setPlatform(e.target.value)}
                  disabled={loading}
                  className="w-full px-3 py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
                  style={{
                    background: "rgba(26,39,68,0.5)",
                    border: "1px solid rgba(99,179,237,0.1)",
                    color: "#e2e8f0",
                  }}
                >
                  <option value="Windows">Windows</option>
                  <option value="Android">Android</option>
                  <option value="macOS">macOS</option>
                  <option value="iOS">iOS</option>
                </select>
              </div>

              {/* Device Count */}
              <div>
                <label className="block text-xs font-semibold mb-2" style={{ color: "#94a3b8" }}>
                  NUMBER OF DEVICES
                </label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={deviceCount}
                  onChange={(e) => setDeviceCount(Math.max(1, parseInt(e.target.value) || 1))}
                  disabled={loading}
                  className="w-full px-3 py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
                  style={{
                    background: "rgba(26,39,68,0.5)",
                    border: "1px solid rgba(99,179,237,0.1)",
                    color: "#e2e8f0",
                  }}
                />
                <p className="text-xs mt-1" style={{ color: "#475569" }}>
                  Creates one enrollment code for {deviceCount} device{deviceCount !== 1 ? "s" : ""}
                </p>
              </div>

              {/* Expiration */}
              <div>
                <label className="block text-xs font-semibold mb-2" style={{ color: "#94a3b8" }}>
                  EXPIRATION (DAYS)
                </label>
                <select
                  value={expirationDays}
                  onChange={(e) => setExpirationDays(parseInt(e.target.value))}
                  disabled={loading}
                  className="w-full px-3 py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
                  style={{
                    background: "rgba(26,39,68,0.5)",
                    border: "1px solid rgba(99,179,237,0.1)",
                    color: "#e2e8f0",
                  }}
                >
                  <option value="1">1 day</option>
                  <option value="3">3 days</option>
                  <option value="7">7 days</option>
                  <option value="30">30 days</option>
                  <option value="90">90 days</option>
                </select>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Success message */}
              <div
                className="p-3 rounded-lg flex items-start gap-3"
                style={{ background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.2)" }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" className="flex-shrink-0 mt-0.5" style={{ color: "#10b981" }}>
                  <path d="M20 6L9 17l-5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <div>
                  <p className="text-sm font-semibold text-green-400">Provisioning Record Created</p>
                  <p className="text-xs mt-1" style={{ color: "#86efac" }}>Share the enrollment code with your devices</p>
                </div>
              </div>

              {/* Enrollment Code */}
              <div>
                <label className="block text-xs font-semibold mb-2" style={{ color: "#94a3b8" }}>
                  ENROLLMENT CODE
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={result.enrollment_code}
                    readOnly
                    className="flex-1 px-3 py-2 rounded-lg text-sm font-mono"
                    style={{
                      background: "rgba(26,39,68,0.5)",
                      border: "1px solid rgba(99,179,237,0.1)",
                      color: "#06b6d4",
                    }}
                  />
                  <button
                    onClick={handleCopyCode}
                    className="px-3 py-2 rounded-lg text-sm font-semibold transition-all hover:opacity-80"
                    style={{
                      background: "rgba(6,182,212,0.1)",
                      border: "1px solid rgba(6,182,212,0.2)",
                      color: "#06b6d4",
                    }}
                  >
                    {copied ? "✓ Copied" : "Copy"}
                  </button>
                </div>
              </div>

              {/* QR Code */}
              {result.qr_data && (
                <div>
                  <label className="block text-xs font-semibold mb-2" style={{ color: "#94a3b8" }}>
                    QR CODE
                  </label>
                  <div
                    className="p-4 rounded-lg flex items-center justify-center"
                    style={{
                      background: "rgba(26,39,68,0.5)",
                      border: "1px solid rgba(99,179,237,0.1)",
                    }}
                  >
                    {/* Display QR code as data URI */}
                    <img
                      src={result.qr_data}
                      alt="QR Code"
                      className="w-40 h-40"
                    />
                  </div>
                  <p className="text-xs mt-2" style={{ color: "#475569" }}>
                    Scan with DataGhost agent to enroll devices
                  </p>
                </div>
              )}

              {/* Details */}
              <div
                className="p-3 rounded-lg space-y-2"
                style={{
                  background: "rgba(26,39,68,0.4)",
                  border: "1px solid rgba(99,179,237,0.1)",
                }}
              >
                <div className="flex justify-between text-xs">
                  <span style={{ color: "#94a3b8" }}>Platform:</span>
                  <span className="text-white font-semibold">{result.platform}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span style={{ color: "#94a3b8" }}>Expires:</span>
                  <span style={{ color: "#f59e0b" }}>{result.expires_at ? new Date(result.expires_at).toLocaleDateString() : "—"}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span style={{ color: "#94a3b8" }}>Status:</span>
                  <span style={{ color: "#10b981" }}>{result.status}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className="px-6 py-4 border-t flex gap-3"
          style={{ borderColor: "rgba(99,179,237,0.1)" }}
        >
          {!result ? (
            <>
              <button
                onClick={onClose}
                disabled={loading}
                className="flex-1 px-4 py-2 rounded-lg text-sm font-semibold transition-colors hover:opacity-80 disabled:opacity-50"
                style={{
                  background: "rgba(99,179,237,0.1)",
                  border: "1px solid rgba(99,179,237,0.2)",
                  color: "#06b6d4",
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={loading}
                className="flex-1 px-4 py-2 rounded-lg text-sm font-semibold transition-all hover:opacity-90 disabled:opacity-50"
                style={{
                  background: "linear-gradient(135deg, #0891b2, #06b6d4)",
                  color: "#fff",
                }}
              >
                {loading ? "Creating…" : "Create Record"}
              </button>
            </>
          ) : (
            <button
              onClick={handleSuccess}
              className="w-full px-4 py-2 rounded-lg text-sm font-semibold transition-all hover:opacity-90"
              style={{
                background: "linear-gradient(135deg, #10b981, #34d058)",
                color: "#fff",
              }}
            >
              Done
            </button>
          )}
        </div>
      </div>
    </>
  );
}
