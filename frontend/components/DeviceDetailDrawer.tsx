"use client";

import { useEffect, useState } from "react";
import { fetchDeviceDetail } from "@/lib/api";
import type { Device, DeviceDetail, IncidentRow } from "@/lib/api";

interface Props {
  device: Device;
  onClose: () => void;
  onResetEnrollment: () => void;
  onDisable: () => void;
  isResetting?: boolean;
  isDisabling?: boolean;
}

export default function DeviceDetailDrawer({
  device,
  onClose,
  onResetEnrollment,
  onDisable,
  isResetting,
  isDisabling,
}: Props) {
  const [detail, setDetail] = useState<DeviceDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadDetail = async () => {
      try {
        setLoading(true);
        const data = await fetchDeviceDetail(device.device_id || "");
        setDetail(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load device details");
      } finally {
        setLoading(false);
      }
    };

    void loadDetail();
  }, [device.device_id]);

  const statusColor = (status: string): string => {
    switch (status) {
      case "ACTIVE":
        return "#10b981";
      case "OFFLINE":
        return "#94a3b8";
      case "DISABLED":
        return "#ef4444";
      default:
        return "#06b6d4";
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40"
        style={{ background: "rgba(3,7,18,0.7)", backdropFilter: "blur(4px)" }}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer panel */}
      <div
        className="fixed right-0 top-0 bottom-0 w-96 z-50 flex flex-col overflow-hidden transition-transform"
        style={{
          background: "#0d1526",
          boxShadow: "-4px 0 20px rgba(0,0,0,0.3)",
        }}
      >
        {/* Header */}
        <div
          className="px-6 py-4 border-b flex items-center justify-between"
          style={{ borderColor: "rgba(99,179,237,0.1)" }}
        >
          <h3 className="text-lg font-semibold text-white">Device Details</h3>
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
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className="h-4 rounded animate-pulse"
                  style={{ background: "rgba(26,39,68,0.4)" }}
                />
              ))}
            </div>
          ) : error ? (
            <div
              className="p-3 rounded-lg"
              style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.2)" }}
            >
              <p className="text-xs text-red-400">Error loading details</p>
            </div>
          ) : (
            <>
              {/* Device ID */}
              <div>
                <p className="text-xs font-semibold" style={{ color: "#94a3b8" }}>DEVICE ID</p>
                <p className="text-sm font-mono mt-1" style={{ color: "#06b6d4" }}>
                  {detail?.device_id || device.device_id}
                </p>
              </div>

              {/* Device Name & Status */}
              <div>
                <p className="text-xs font-semibold" style={{ color: "#94a3b8" }}>NAME / STATUS</p>
                <div className="flex items-center gap-2 mt-1">
                  <span
                    className="inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-semibold"
                    style={{
                      background: `${statusColor(device.status)}15`,
                      color: statusColor(device.status),
                    }}
                  >
                    ● {device.status}
                  </span>
                  <p className="text-sm text-white">{device.device_name}</p>
                </div>
              </div>

              {/* Platform / OS */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs font-semibold" style={{ color: "#94a3b8" }}>PLATFORM</p>
                  <p className="text-sm mt-1 text-white">{device.platform || device.os_type || "—"}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold" style={{ color: "#94a3b8" }}>OS VERSION</p>
                  <p className="text-sm mt-1 text-white">{device.os_version || "—"}</p>
                </div>
              </div>

              {/* IP & Hostname */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs font-semibold" style={{ color: "#94a3b8" }}>IP ADDRESS</p>
                  <p className="text-sm font-mono mt-1" style={{ color: "#06b6d4" }}>
                    {device.ip_address}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold" style={{ color: "#94a3b8" }}>HOSTNAME</p>
                  <p className="text-sm mt-1 text-white">{device.hostname || "—"}</p>
                </div>
              </div>

              {/* Agent Version */}
              <div>
                <p className="text-xs font-semibold" style={{ color: "#94a3b8" }}>AGENT VERSION</p>
                <p className="text-sm font-mono mt-1" style={{ color: "#10b981" }}>
                  {device.agent_version || "Unknown"}
                </p>
              </div>

              {/* Files Scanned */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs font-semibold" style={{ color: "#94a3b8" }}>FILES SCANNED</p>
                  <p className="text-xl font-bold mt-1" style={{ color: "#06b6d4" }}>
                    {device.files_scanned?.toLocaleString() ?? "—"}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold" style={{ color: "#94a3b8" }}>INCIDENTS</p>
                  <p className="text-xl font-bold mt-1" style={{ color: "#ef4444" }}>
                    {device.incidents_count ?? "—"}
                  </p>
                </div>
              </div>

              {/* Enrollment & Last Seen */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs font-semibold" style={{ color: "#94a3b8" }}>ENROLLED</p>
                  <p className="text-xs mt-1" style={{ color: "#475569" }}>
                    {device.enrolled_at
                      ? new Date(device.enrolled_at).toLocaleDateString()
                      : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold" style={{ color: "#94a3b8" }}>LAST SEEN</p>
                  <p className="text-xs mt-1" style={{ color: "#475569" }}>
                    {device.last_seen
                      ? new Date(device.last_seen).toLocaleDateString()
                      : "—"}
                  </p>
                </div>
              </div>

              {/* Recent Incidents */}
              {detail?.recent_incidents && detail.recent_incidents.length > 0 && (
                <div>
                  <p className="text-xs font-semibold mb-2" style={{ color: "#94a3b8" }}>
                    RECENT INCIDENTS ({detail.recent_incidents.length})
                  </p>
                  <div className="space-y-2">
                    {detail.recent_incidents.slice(0, 3).map((incident) => (
                      <div
                        key={incident.incident_id}
                        className="p-2 rounded text-xs"
                        style={{
                          background: "rgba(26,39,68,0.4)",
                          border: "1px solid rgba(99,179,237,0.1)",
                        }}
                      >
                        <p className="text-white truncate">{incident.filename}</p>
                        <p style={{ color: "#94a3b8" }}>
                          {incident.severity} • {new Date(incident.timestamp).toLocaleDateString()}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer actions */}
        <div
          className="px-6 py-4 border-t space-y-2"
          style={{ borderColor: "rgba(99,179,237,0.1)" }}
        >
          <button
            onClick={onResetEnrollment}
            disabled={isResetting || device.status === "DISABLED"}
            className="w-full px-4 py-2 rounded-lg text-sm font-semibold transition-all hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              background: "rgba(245,158,11,0.1)",
              border: "1px solid rgba(245,158,11,0.2)",
              color: "#f59e0b",
            }}
          >
            {isResetting ? "Resetting…" : "Reset Enrollment"}
          </button>

          <button
            onClick={onDisable}
            disabled={isDisabling || device.status === "DISABLED"}
            className="w-full px-4 py-2 rounded-lg text-sm font-semibold transition-all hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              background: "rgba(239,68,68,0.1)",
              border: "1px solid rgba(239,68,68,0.2)",
              color: "#ef4444",
            }}
          >
            {isDisabling ? "Disabling…" : "Disable Device"}
          </button>

          <button
            onClick={onClose}
            className="w-full px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
            style={{
              background: "rgba(99,179,237,0.1)",
              border: "1px solid rgba(99,179,237,0.2)",
              color: "#06b6d4",
            }}
          >
            Close
          </button>
        </div>
      </div>
    </>
  );
}
