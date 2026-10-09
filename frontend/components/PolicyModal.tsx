"use client";

import { useState } from "react";
import { createEnrollmentPolicy } from "@/lib/api";

interface Props {
  onClose: () => void;
  onSuccess: () => void;
}

export default function PolicyModal({ onClose, onSuccess }: Props) {
  const [name, setName] = useState("");
  const [platform, setPlatform] = useState("Windows");
  const [complianceLevel, setComplianceLevel] = useState("MEDIUM");
  const [requireAttestation, setRequireAttestation] = useState(false);
  const [selectedRules, setSelectedRules] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Mock available rules for demonstration
  const availableRules = [
    { id: "rule-1", name: "Encrypt Sensitive Files", category: "DATA_PROTECTION" },
    { id: "rule-2", name: "Block External USB Transfers", category: "EXFILTRATION" },
    { id: "rule-3", name: "Monitor Database Access", category: "DATABASE" },
    { id: "rule-4", name: "Audit Email Attachments", category: "EMAIL" },
    { id: "rule-5", name: "Control Cloud Storage", category: "CLOUD" },
  ];

  const handleCreate = async () => {
    if (!name.trim()) {
      setError("Policy name is required");
      return;
    }

    try {
      setLoading(true);
      setError(null);

      await createEnrollmentPolicy(
        name,
        platform,
        "default-org", // Organization ID - would come from context
        selectedRules,
        complianceLevel,
        requireAttestation
      );

      setSuccess(true);
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create enrollment policy");
    } finally {
      setLoading(false);
    }
  };

  const toggleRule = (ruleId: string) => {
    setSelectedRules((prev) =>
      prev.includes(ruleId)
        ? prev.filter((r) => r !== ruleId)
        : [...prev, ruleId]
    );
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
            <h2 className="text-lg font-semibold text-white">Create Enrollment Policy</h2>
            <p className="text-xs mt-1" style={{ color: "#94a3b8" }}>
              Define compliance rules and requirements for device enrollment
            </p>
          </div>
          <button
            onClick={onClose}
            disabled={loading}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/50 transition-colors disabled:opacity-50"
            aria-label="Close"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-4 max-h-96 overflow-y-auto space-y-4">
          {success && (
            <div
              className="p-3 rounded-lg flex items-start gap-3"
              style={{ background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.2)" }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" className="flex-shrink-0 mt-0.5" style={{ color: "#10b981" }}>
                <path d="M20 6L9 17l-5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <p className="text-sm font-semibold text-green-400">Policy created successfully!</p>
            </div>
          )}

          {error && (
            <div
              className="p-3 rounded-lg"
              style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.2)" }}
            >
              <p className="text-xs font-semibold text-red-400">Error</p>
              <p className="text-xs mt-1" style={{ color: "#f87171" }}>{error}</p>
            </div>
          )}

          {!success && (
            <>
              {/* Policy Name */}
              <div>
                <label className="block text-xs font-semibold mb-2" style={{ color: "#94a3b8" }}>
                  POLICY NAME
                </label>
                <input
                  type="text"
                  placeholder="e.g., Corporate Devices"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={loading}
                  className="w-full px-3 py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
                  style={{
                    background: "rgba(26,39,68,0.5)",
                    border: "1px solid rgba(99,179,237,0.1)",
                    color: "#e2e8f0",
                  }}
                />
              </div>

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

              {/* Compliance Level */}
              <div>
                <label className="block text-xs font-semibold mb-2" style={{ color: "#94a3b8" }}>
                  COMPLIANCE LEVEL
                </label>
                <select
                  value={complianceLevel}
                  onChange={(e) => setComplianceLevel(e.target.value)}
                  disabled={loading}
                  className="w-full px-3 py-2 rounded-lg text-sm transition-colors disabled:opacity-50"
                  style={{
                    background: "rgba(26,39,68,0.5)",
                    border: "1px solid rgba(99,179,237,0.1)",
                    color: "#e2e8f0",
                  }}
                >
                  <option value="LOW">Low (Basic DLP)</option>
                  <option value="MEDIUM">Medium (Standard)</option>
                  <option value="HIGH">High (Strict)</option>
                </select>
              </div>

              {/* DLP Rules */}
              <div>
                <label className="block text-xs font-semibold mb-2" style={{ color: "#94a3b8" }}>
                  SELECT DLP RULES
                </label>
                <div className="space-y-2">
                  {availableRules.map((rule) => (
                    <label
                      key={rule.id}
                      className="flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-colors hover:bg-slate-800/50"
                      style={{
                        background: "rgba(26,39,68,0.3)",
                        border: "1px solid rgba(99,179,237,0.1)",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={selectedRules.includes(rule.id)}
                        onChange={() => toggleRule(rule.id)}
                        disabled={loading}
                        className="w-4 h-4 rounded"
                        style={{
                          accentColor: "#06b6d4",
                          cursor: "pointer",
                        }}
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-white">{rule.name}</p>
                        <p className="text-xs" style={{ color: "#475569" }}>
                          {rule.category}
                        </p>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Require Attestation */}
              <div className="flex items-center gap-3 p-3 rounded-lg"
                style={{
                  background: "rgba(26,39,68,0.3)",
                  border: "1px solid rgba(99,179,237,0.1)",
                }}>
                <input
                  type="checkbox"
                  id="attestation"
                  checked={requireAttestation}
                  onChange={(e) => setRequireAttestation(e.target.checked)}
                  disabled={loading}
                  className="w-4 h-4 rounded"
                  style={{
                    accentColor: "#06b6d4",
                    cursor: "pointer",
                  }}
                />
                <label htmlFor="attestation" className="flex-1 cursor-pointer">
                  <p className="text-sm font-semibold text-white">Require Device Attestation</p>
                  <p className="text-xs" style={{ color: "#475569" }}>
                    Verify device integrity before enrollment (TPM, SafetyNet, etc.)
                  </p>
                </label>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div
          className="px-6 py-4 border-t flex gap-3"
          style={{ borderColor: "rgba(99,179,237,0.1)" }}
        >
          {!success ? (
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
                disabled={loading || !name.trim()}
                className="flex-1 px-4 py-2 rounded-lg text-sm font-semibold transition-all hover:opacity-90 disabled:opacity-50"
                style={{
                  background: "linear-gradient(135deg, #0891b2, #06b6d4)",
                  color: "#fff",
                }}
              >
                {loading ? "Creating…" : "Create Policy"}
              </button>
            </>
          ) : (
            <button
              onClick={() => {
                onSuccess();
                onClose();
              }}
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
