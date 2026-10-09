"use client";

import { useEffect, useState, useCallback } from "react";
import { useAuthContext } from "@/lib/AuthContext";
import { fetchDevices, resetDeviceEnrollment, disableDevice } from "@/lib/api";
import type { Device } from "@/lib/api";
import DeviceDetailDrawer from "@/components/DeviceDetailDrawer";
import { AuthError } from "@/lib/auth";

export default function DevicesPage() {
  const { signalAuthFailure } = useAuthContext();

  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [platformFilter, setPlatformFilter] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
  const [resettingId, setResettingId] = useState<string | null>(null);
  const [disablingId, setDisablingId] = useState<string | null>(null);

  const loadDevices = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchDevices();
      setDevices(data);
    } catch (err) {
      if (err instanceof AuthError) {
        signalAuthFailure();
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to load devices");
    } finally {
      setLoading(false);
    }
  }, [signalAuthFailure]);

  useEffect(() => {
    loadDevices();
  }, [loadDevices]);

  const filteredDevices = devices.filter((device) => {
    if (platformFilter !== "ALL" && device.platform !== platformFilter) return false;
    if (statusFilter !== "ALL" && device.status !== statusFilter) return false;
    if (searchTerm && !device.device_name?.toLowerCase().includes(searchTerm.toLowerCase()) &&
        !device.device_id?.toLowerCase().includes(searchTerm.toLowerCase())) {
      return false;
    }
    return true;
  });

  const handleResetEnrollment = async (deviceId: string) => {
    if (!confirm("Reset device enrollment? The device will need to re-enroll on next startup.")) {
      return;
    }

    try {
      setResettingId(deviceId);
      await resetDeviceEnrollment(deviceId);
      setDevices((prev) =>
        prev.map((d) => d.device_id === deviceId ? { ...d, status: "OFFLINE" } : d)
      );
    } catch (err) {
      if (err instanceof AuthError) {
        signalAuthFailure();
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to reset enrollment");
    } finally {
      setResettingId(null);
    }
  };

  const handleDisableDevice = async (deviceId: string) => {
    if (!confirm("Disable this device? It will no longer be able to authenticate.")) {
      return;
    }

    try {
      setDisablingId(deviceId);
      await disableDevice(deviceId);
      setDevices((prev) =>
        prev.map((d) => d.device_id === deviceId ? { ...d, status: "DISABLED" } : d)
      );
      setSelectedDevice(null);
    } catch (err) {
      if (err instanceof AuthError) {
        signalAuthFailure();
        return;
      }
      setError(err instanceof Error ? err.message : "Failed to disable device");
    } finally {
      setDisablingId(null);
    }
  };

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

  const statusIcon = (status: string): string => {
    switch (status) {
      case "ACTIVE":
        return "●";
      case "OFFLINE":
        return "◐";
      case "DISABLED":
        return "✕";
      default:
        return "?";
    }
  };

  return (
    <div className="p-4 md:p-6">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-white mb-2">Enrolled Devices</h2>
        <p className="text-sm" style={{ color: "#94a3b8" }}>
          View and manage all devices enrolled in your DataGhost organization
        </p>
      </div>

      {/* Controls */}
      <div className="mb-6 space-y-3">
        <div className="flex gap-3">
          <input
            type="text"
            placeholder="Search by device name or ID…"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="flex-1 px-3 py-2 rounded-lg text-sm transition-colors"
            style={{
              background: "rgba(26,39,68,0.5)",
              border: "1px solid rgba(99,179,237,0.1)",
              color: "#e2e8f0",
            }}
          />

          <select
            value={platformFilter}
            onChange={(e) => setPlatformFilter(e.target.value)}
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
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer"
            style={{
              background: "rgba(26,39,68,0.5)",
              border: "1px solid rgba(99,179,237,0.1)",
              color: "#e2e8f0",
            }}
          >
            <option value="ALL">All Status</option>
            <option value="ACTIVE">Active</option>
            <option value="OFFLINE">Offline</option>
            <option value="DISABLED">Disabled</option>
          </select>

          <button
            onClick={() => void loadDevices()}
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
            onClick={() => void loadDevices()}
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

      {/* Empty state */}
      {!loading && filteredDevices.length === 0 && (
        <div
          className="dg-card py-12 text-center"
          style={{ border: "2px dashed rgba(99,179,237,0.2)" }}
        >
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" className="mx-auto mb-3 opacity-50">
            <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.5" />
            <path d="M12 7v5l3.5 1.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <p className="text-sm font-semibold text-white">No devices found</p>
          <p className="text-xs mt-1" style={{ color: "#475569" }}>
            {devices.length === 0 ? "No enrolled devices yet" : "Try adjusting your filters"}
          </p>
        </div>
      )}

      {/* Devices table */}
      {!loading && filteredDevices.length > 0 && (
        <div className="dg-card p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full data-table">
              <thead>
                <tr>
                  <th>Device ID</th>
                  <th>Name</th>
                  <th>Platform</th>
                  <th>Status</th>
                  <th>Agent Version</th>
                  <th>IP Address</th>
                  <th>Last Seen</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredDevices.map((device) => (
                  <tr key={device.device_id} className="hover:opacity-75 transition-opacity cursor-pointer"
                    onClick={() => setSelectedDevice(device)}>
                    <td className="font-mono text-xs" style={{ color: "#06b6d4" }}>
                      {device.device_id?.substring(0, 12)}…
                    </td>
                    <td className="text-sm font-semibold text-white">{device.device_name}</td>
                    <td className="text-sm">{device.platform || device.os_type}</td>
                    <td>
                      <span
                        className="inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-semibold"
                        style={{
                          background: `${statusColor(device.status)}15`,
                          color: statusColor(device.status),
                        }}
                      >
                        <span>{statusIcon(device.status)}</span>
                        {device.status}
                      </span>
                    </td>
                    <td className="text-xs" style={{ color: "#94a3b8" }}>
                      {device.agent_version || "—"}
                    </td>
                    <td className="text-xs font-mono" style={{ color: "#94a3b8" }}>
                      {device.ip_address}
                    </td>
                    <td className="text-xs" style={{ color: "#94a3b8" }}>
                      {device.last_seen
                        ? new Date(device.last_seen).toLocaleDateString()
                        : "—"}
                    </td>
                    <td className="text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleResetEnrollment(device.device_id || "");
                        }}
                        disabled={resettingId === device.device_id}
                        className="px-2 py-1 text-xs font-semibold rounded transition-colors hover:bg-amber-500/20 disabled:opacity-50"
                        style={{ color: "#f59e0b" }}
                      >
                        {resettingId === device.device_id ? "…" : "Reset"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Result count */}
      {!loading && filteredDevices.length > 0 && (
        <div className="mt-4 text-xs" style={{ color: "#94a3b8" }}>
          Showing {filteredDevices.length} of {devices.length} device{devices.length !== 1 ? "s" : ""}
        </div>
      )}

      {/* Device detail drawer */}
      {selectedDevice && (
        <DeviceDetailDrawer
          device={selectedDevice}
          onClose={() => setSelectedDevice(null)}
          onResetEnrollment={() => {
            setSelectedDevice(null);
            handleResetEnrollment(selectedDevice.device_id || "");
          }}
          onDisable={() => handleDisableDevice(selectedDevice.device_id || "")}
          isResetting={resettingId === selectedDevice.device_id}
          isDisabling={disablingId === selectedDevice.device_id}
        />
      )}
    </div>
  );
}
