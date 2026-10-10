"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import QRCode from "qrcode";
import Sidebar, { toggleSidebar } from "../../components/Sidebar";
import {
  fetchDevices,
  createEnrollmentToken,
  createEasyEnrollmentToken,
  createAndroidEnterpriseEnrollmentToken,
  fetchEnrollmentStatus,
  registerEnrollmentDevice,
  fetchDeviceDetail,
  updateDevice,
  deleteDevice,
  triggerDeviceScan,
  scanFile,
} from "@/lib/api";
import type {
  Device,
  EnrollmentCreateResponse,
  DeviceDetail,
} from "@/lib/api";
import { useAuthGuard } from "@/lib/useAuthGuard";

// ─── Platform Configuration ───────────────────────────────────────────────────
type PlatformType = "Windows" | "Linux" | "macOS" | "Android" | "iOS";

const PLATFORMS: { id: PlatformType; label: string; icon: string; desc: string }[] = [
  { id: "Windows", label: "Windows", icon: "🪟", desc: "Windows 10/11 x64 Agent" },
  { id: "Linux", label: "Linux", icon: "🐧", desc: "Ubuntu / RHEL / Debian Server & Desktop" },
  { id: "macOS", label: "macOS", icon: "🍎", desc: "macOS Sonoma / Ventura Apple & Intel" },
  { id: "Android", label: "Android", icon: "🤖", desc: "Easy Enrollment or Android Enterprise Fully Managed" },
  { id: "iOS", label: "iOS", icon: "📱", desc: "iOS MDM Managed Endpoint App" },
];

// Android enrollment: top-level type choice
type AndroidEnrollType = "easy" | "enterprise" | null;
// Android enterprise sub-mode (kept for Fully Managed path)
type AndroidEnrollmentMode = "work_profile" | "fully_managed" | null;

function getPlatformIcon(platform?: string, osType?: string): string {
  const p = (platform || osType || "").toLowerCase();
  if (p.includes("win")) return "🪟";
  if (p.includes("linux")) return "🐧";
  if (p.includes("mac") || p.includes("darwin")) return "🍎";
  if (p.includes("android")) return "🤖";
  if (p.includes("ios") || p.includes("iphone") || p.includes("ipad")) return "📱";
  return "🖥️";
}

function timeAgo(ts?: string | null): string {
  if (!ts) return "Never";
  const diff = (Date.now() - new Date(ts).getTime()) / 1000;
  if (diff < 5) return "Just now";
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function formatDate(ts?: string | null): string {
  if (!ts) return "N/A";
  try {
    return new Date(ts).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return ts;
  }
}

function PlatformBadge({ platform }: { platform?: string }) {
  const p = (platform || "Windows").toLowerCase();
  let bg = "rgba(148,163,184,0.1)";
  let color = "#94a3b8";

  if (p.includes("win")) { bg = "rgba(96,165,250,0.1)"; color = "#60a5fa"; }
  else if (p.includes("linux")) { bg = "rgba(255,159,10,0.1)"; color = "#ff9f0a"; }
  else if (p.includes("mac")) { bg = "rgba(167,139,250,0.1)"; color = "#a78bfa"; }
  else if (p.includes("android")) { bg = "rgba(52,208,88,0.1)"; color = "#34d058"; }
  else if (p.includes("ios")) { bg = "rgba(0,212,255,0.1)"; color = "#00d4ff"; }

  return (
    <span
      className="text-[10px] font-semibold px-2 py-0.5 rounded"
      style={{ background: bg, color: color, border: `1px solid ${color}25` }}
    >
      {platform || "Endpoint"}
    </span>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
export default function DevicesPage() {
  const checked = useAuthGuard();

  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // --- Selection and Bulk Actions State ---
  const [selectedDeviceIds, setSelectedDeviceIds] = useState<string[]>([]);
  const [bulkDeleting, setBulkDeleting] = useState(false);

  // --- Add Device Modal state ---
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedPlatform, setSelectedPlatform] = useState<PlatformType>("Windows");
  const [addModalStep, setAddModalStep] = useState<"platform" | "android_type" | "android_enterprise">("platform");
  // Android enrollment: top-level type (easy vs enterprise)
  const [androidEnrollType, setAndroidEnrollType] = useState<AndroidEnrollType>(null);
  // Android enterprise sub-mode
  const [androidMode, setAndroidMode] = useState<AndroidEnrollmentMode>(null);
  const [generatingCode, setGeneratingCode] = useState(false);
  const [enrollmentData, setEnrollmentData] = useState<EnrollmentCreateResponse | null>(null);
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);
  const [enrollmentStatus, setEnrollmentStatus] = useState<"PENDING" | "USED" | "EXPIRED" | "CANCELLED">("PENDING");
  const [enrolledDeviceName, setEnrolledDeviceName] = useState<string | null>(null);
  const [timeLeft, setTimeLeft] = useState<number>(600);
  const [copySuccess, setCopySuccess] = useState(false);
  const [copyUrlSuccess, setCopyUrlSuccess] = useState(false);
  const [modalAutoEnrolling, setModalAutoEnrolling] = useState(false);
  const [batchEnrolling, setBatchEnrolling] = useState(false);

  // Auto-enroll the currently active modal session instantly
  const handleAutoEnrollCurrentModal = async () => {
    if (!enrollmentData?.enrollment_code) return;
    setModalAutoEnrolling(true);
    try {
      const code = enrollmentData.enrollment_code;
      const plat = selectedPlatform || "Windows";
      const devName = `${plat}-Endpoint-${code.replace(/[^A-Z0-9]/g, "").slice(-4) || "01"}`;
      await registerEnrollmentDevice({
        enrollment_code: code,
        device_name: devName,
        platform: plat,
        os_name: `${plat} Enterprise`,
        hostname: `${plat.toUpperCase()}-NODE-${code.replace(/[^A-Z0-9]/g, "").slice(-4) || "01"}`,
      });
      setEnrolledDeviceName(devName);
      setEnrollmentStatus("USED");
      await loadDevices(false);
    } catch (err: unknown) {
      console.error("Auto-enroll modal device error:", err);
    } finally {
      setModalAutoEnrolling(false);
    }
  };

  // Detect the actual host platform from the browser
  const detectHostPlatform = (): { platform: PlatformType; osName: string; hostname: string; osVersion: string } => {
    const ua = navigator.userAgent.toLowerCase();
    const plat = (navigator as any).userAgentData?.platform?.toLowerCase?.() || navigator.platform?.toLowerCase() || "";

    // Extract OS version from user-agent string
    let osVersion = "";
    const winMatch = ua.match(/windows nt ([\d.]+)/);
    const macMatch = ua.match(/mac os x ([\d_]+)/);
    const androidMatch = ua.match(/android ([\d.]+)/);
    if (winMatch) osVersion = `Windows ${winMatch[1] === "10.0" ? "10/11" : winMatch[1]}`;
    else if (macMatch) osVersion = `macOS ${macMatch[1].replace(/_/g, ".")}`;
    else if (androidMatch) osVersion = `Android ${androidMatch[1]}`;

    if (ua.includes("android")) return { platform: "Android", osName: "Android", hostname: "ANDROID-DEVICE", osVersion: osVersion || "Android" };
    if (ua.includes("iphone") || ua.includes("ipad") || ua.includes("ipod")) return { platform: "iOS", osName: "iOS", hostname: "IOS-DEVICE", osVersion: "iOS" };
    if (plat.includes("mac") || ua.includes("macintosh")) return { platform: "macOS", osName: "macOS", hostname: "MAC-WORKSTATION", osVersion: osVersion || "macOS" };
    if (plat.includes("linux") || ua.includes("linux")) return { platform: "Linux", osName: "Linux", hostname: "LINUX-WORKSTATION", osVersion: "Linux" };
    return { platform: "Windows", osName: "Windows", hostname: "WINDOWS-WORKSTATION", osVersion: osVersion || "Windows 10/11" };
  };

  // Automatically provision and enroll this device (detected from the browser)
  const handleAutoEnrollThisDevice = async () => {
    setBatchEnrolling(true);
    try {
      const host = detectHostPlatform();
      const tokenRes = await createEnrollmentToken(host.platform);
      if (tokenRes?.enrollment_code) {
        // Unique device name: platform + last 4 chars of code to avoid duplicates
        const suffix = tokenRes.enrollment_code.replace(/[^A-Z0-9]/g, "").slice(-4) || "0001";
        const deviceName = `${host.hostname}-${suffix}`;
        await registerEnrollmentDevice({
          enrollment_code: tokenRes.enrollment_code,
          device_name: deviceName,
          platform: host.platform,
          os_name: host.osVersion,
          os_version: host.osVersion,
          hostname: deviceName,
        });
      }
      await loadDevices(true);
    } catch (err: unknown) {
      console.error("Auto-enroll error:", err);
      alert(err instanceof Error ? err.message : "Auto-enrollment failed. Please try again.");
    } finally {
      setBatchEnrolling(false);
    }
  };


  // --- Device Details Modal state ---
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
  const [deviceDetail, setDeviceDetail] = useState<DeviceDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [scanLoadingDevice, setScanLoadingDevice] = useState<string | null>(null);
  const [scanResultData, setScanResultData] = useState<any | null>(null);

  // Ref for polling timer cleanup
  const statusPollRef = useRef<NodeJS.Timeout | null>(null);
  const countdownRef = useRef<NodeJS.Timeout | null>(null);

  // --- Fetch devices list ---
  const loadDevices = useCallback(async (showSpinner = true) => {
    if (showSpinner) setLoading(true);
    setError(null);
    try {
      const data = await fetchDevices();
      setDevices(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load devices");
    } finally {
      if (showSpinner) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (checked) {
      loadDevices(true);
      const interval = setInterval(() => loadDevices(false), 8000);
      return () => clearInterval(interval);
    }
  }, [checked, loadDevices]);

  useEffect(() => {
    return () => {
      if (statusPollRef.current) clearInterval(statusPollRef.current);
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, []);

  // --- Generate Enrollment Token ---
  // mode: 'easy' = URL QR (no factory reset), 'enterprise' = Android DPC QR, 'standard' = other platforms
  const handleGenerateEnrollment = async (mode: "easy" | "enterprise" | "standard" = "standard") => {
    setGeneratingCode(true);
    setError(null);
    setEnrollmentData(null);
    setQrDataUrl(null);
    setEnrollmentStatus("PENDING");
    setEnrolledDeviceName(null);

    try {
      let res;
      const targetPlatform = selectedPlatform || "Android";
      if (mode === "easy") {
        res = await createEasyEnrollmentToken(targetPlatform);
      } else if (mode === "enterprise") {
        res = await createAndroidEnterpriseEnrollmentToken();
      } else {
        res = await createEnrollmentToken(targetPlatform);
      }

      setEnrollmentData(res);
      setTimeLeft(res.expires_in_seconds || 600);

      // For easy enrollment, QR data is a plain URL; for enterprise it's JSON
      const qrContent = res.qr_data;
      try {
        const qrColor = mode === "easy" ? "#34d058" : "#00d4ff";
        const qrUrl = await QRCode.toDataURL(qrContent, {
          margin: 1,
          width: 220,
          color: { dark: qrColor, light: "#090f1d" },
        });
        setQrDataUrl(qrUrl);
      } catch (qrErr) {
        console.error("QR Code generation error:", qrErr);
      }

      // Start countdown timer
      if (countdownRef.current) clearInterval(countdownRef.current);
      countdownRef.current = setInterval(() => {
        setTimeLeft((prev) => {
          if (prev <= 1) {
            if (countdownRef.current) clearInterval(countdownRef.current);
            setEnrollmentStatus("EXPIRED");
            return 0;
          }
          return prev - 1;
        });
      }, 1000);

      // Start polling status every 2 seconds
      if (statusPollRef.current) clearInterval(statusPollRef.current);
      statusPollRef.current = setInterval(async () => {
        try {
          const st = await fetchEnrollmentStatus(res.enrollment_code);
          if (st.status === "USED") {
            setEnrollmentStatus("USED");
            setEnrolledDeviceName(st.device_name || "New Device");
            if (statusPollRef.current) clearInterval(statusPollRef.current);
            if (countdownRef.current) clearInterval(countdownRef.current);
            loadDevices(false);
          } else if (st.status === "EXPIRED" || st.is_expired) {
            setEnrollmentStatus("EXPIRED");
            if (statusPollRef.current) clearInterval(statusPollRef.current);
            if (countdownRef.current) clearInterval(countdownRef.current);
          }
        } catch {
          // Ignore transient poll errors
        }
      }, 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate enrollment");
    } finally {
      setGeneratingCode(false);
    }
  };

  const closeAddModal = () => {
    setShowAddModal(false);
    setEnrollmentData(null);
    setQrDataUrl(null);
    setEnrollmentStatus("PENDING");
    setAndroidMode(null);
    setAndroidEnrollType(null);
    setAddModalStep("platform");
    setCopySuccess(false);
    setCopyUrlSuccess(false);
    if (statusPollRef.current) clearInterval(statusPollRef.current);
    if (countdownRef.current) clearInterval(countdownRef.current);
  };

  const handleCopyCode = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopySuccess(true);
    setTimeout(() => setCopySuccess(false), 2000);
  };

  const handleCopyUrl = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopyUrlSuccess(true);
    setTimeout(() => setCopyUrlSuccess(false), 2000);
  };

  const handleDeviceClick = async (device: Device) => {
    setSelectedDevice(device);
    setLoadingDetail(true);
    setDeviceDetail(null);
    setShowDeleteConfirm(false);
    try {
      const devId = device.device_id || String(device.id);
      const detail = await fetchDeviceDetail(devId);
      setDeviceDetail(detail);
    } catch {
      setDeviceDetail({
        ...device,
        policy_status: device.status !== "DISABLED" ? "Enforced" : "Disabled",
      });
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleToggleStatus = async () => {
    if (!selectedDevice) return;
    setActionLoading(true);
    const newStatus = selectedDevice.status === "DISABLED" ? "ACTIVE" : "DISABLED";
    try {
      const devId = selectedDevice.device_id || String(selectedDevice.id);
      const updated = await updateDevice(devId, { status: newStatus });
      setSelectedDevice(updated);
      setDeviceDetail((prev) => prev ? { ...prev, status: updated.status, policy_status: updated.status !== "DISABLED" ? "Enforced" : "Disabled" } : null);
      loadDevices(false);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to update device status");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRemoveDevice = async () => {
    if (!selectedDevice) return;
    setActionLoading(true);
    try {
      const devId = selectedDevice.device_id || String(selectedDevice.id);
      await deleteDevice(devId);
      setSelectedDevice(null);
      setDeviceDetail(null);
      setShowDeleteConfirm(false);
      loadDevices(true);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to remove device");
    } finally {
      setActionLoading(false);
    }
  };

  // Quick action: Run DLP file scan on device & get all information
  const handleQuickScan = async (e: React.MouseEvent, dev: Device) => {
    e.stopPropagation();
    const devId = dev.device_id || String(dev.id);
    setScanLoadingDevice(devId);
    try {
      const data = await triggerDeviceScan(devId);
      setScanResultData(data);
      await loadDevices(false);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to run scan on device");
    } finally {
      setScanLoadingDevice(null);
    }
  };

  // Quick action: Deactivate or Activate device
  const handleQuickToggle = async (e: React.MouseEvent, dev: Device) => {
    e.stopPropagation();
    const devId = dev.device_id || String(dev.id);
    const newStatus = dev.status === "DISABLED" ? "ACTIVE" : "DISABLED";
    try {
      await updateDevice(devId, { status: newStatus });
      await loadDevices(false);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to toggle device status");
    }
  };

  // Quick action: Remove device
  const handleQuickDelete = async (e: React.MouseEvent, dev: Device) => {
    e.stopPropagation();
    const devId = dev.device_id || String(dev.id);
    if (!window.confirm(`Are you sure you want to remove endpoint device '${dev.device_name}'?`)) {
      return;
    }
    try {
      await deleteDevice(devId);
      setSelectedDeviceIds((prev) => prev.filter((id) => id !== devId));
      await loadDevices(true);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to remove device");
    }
  };

  // --- Selection and Bulk Delete logic ---
  const isDeviceSelected = (devId: string) => selectedDeviceIds.includes(devId);

  const toggleSelectDevice = (e: React.MouseEvent, devId: string) => {
    e.stopPropagation();
    setSelectedDeviceIds((prev) =>
      prev.includes(devId) ? prev.filter((id) => id !== devId) : [...prev, devId]
    );
  };

  const handleSelectAllDevices = () => {
    const allIds = devices.map((d) => d.device_id || String(d.id));
    if (selectedDeviceIds.length === allIds.length && allIds.length > 0) {
      setSelectedDeviceIds([]);
    } else {
      setSelectedDeviceIds(allIds);
    }
  };

  const handleBulkDeleteDevices = async () => {
    if (selectedDeviceIds.length === 0) return;
    if (!window.confirm(`Are you sure you want to remove ${selectedDeviceIds.length} selected device(s)?`)) return;
    setBulkDeleting(true);
    try {
      await Promise.all(selectedDeviceIds.map((id) => deleteDevice(id)));
      setSelectedDeviceIds([]);
      await loadDevices(true);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to remove selected devices");
    } finally {
      setBulkDeleting(false);
    }
  };

  const handleBulkDeactivateDevices = async () => {
    if (selectedDeviceIds.length === 0) return;
    setBulkDeleting(true);
    try {
      await Promise.all(selectedDeviceIds.map((id) => updateDevice(id, { status: "DISABLED" })));
      setSelectedDeviceIds([]);
      await loadDevices(false);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to deactivate selected devices");
    } finally {
      setBulkDeleting(false);
    }
  };

  // --- Dynamic Dashboard Stats ---
  const activeCount = devices.filter((d) => d.status === "ACTIVE").length;
  const countByPlatform = (p: string) =>
    devices.filter((d) => {
      const devPlat = (d.platform || d.os_type || "").toLowerCase();
      return devPlat.includes(p.toLowerCase());
    }).length;

  const winCount = countByPlatform("win");
  const linuxCount = countByPlatform("linux");
  const macCount = countByPlatform("mac") + countByPlatform("darwin");
  const androidCount = countByPlatform("android");
  const iosCount = countByPlatform("ios");

  // Step logic for Add Device modal:
  // Step 1: Platform Selection ('platform')
  // Step 2a: Android Method Selection ('android_type')
  // Step 2b: Android Enterprise Sub-mode Selection ('android_enterprise')
  // Step 3: QR Code & Codes display (when enrollmentData is present)
  const showPlatformStep = !enrollmentData && addModalStep === "platform";
  const showAndroidEnrollTypeStep = !enrollmentData && addModalStep === "android_type";
  const showAndroidModeStep = !enrollmentData && addModalStep === "android_enterprise";


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
            <h1 className="text-lg font-bold text-white">Devices</h1>
            <span
              className="px-2.5 py-1 rounded-full text-xs font-bold"
              style={{
                background: "rgba(52,208,88,0.1)",
                color: "#34d058",
                border: "1px solid rgba(52,208,88,0.2)",
              }}
            >
              {activeCount} active
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                setShowAddModal(true);
                setEnrollmentData(null);
                setQrDataUrl(null);
                setEnrollmentStatus("PENDING");
                setAndroidMode(null);
              }}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold text-white transition-all shadow-md hover:brightness-110 active:scale-95"
              style={{
                background: "linear-gradient(135deg, #0089b2, #00d4ff)",
                border: "1px solid rgba(0,212,255,0.4)",
              }}
            >
              <span className="text-sm font-bold">+</span> Add Device
            </button>

            <button
              type="button"
              onClick={handleAutoEnrollThisDevice}
              disabled={batchEnrolling}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-cyan-300 transition-all hover:bg-cyan-500/10 active:scale-95 disabled:opacity-50"
              style={{
                background: "rgba(0,212,255,0.06)",
                border: "1px solid rgba(0,212,255,0.3)",
              }}
              title="Automatically detects this machine and enrolls it as an endpoint"
            >
              {batchEnrolling ? (
                <>
                  <span className="w-3 h-3 border-2 border-cyan-400/20 border-t-cyan-400 rounded-full animate-spin" />
                  <span>Enrolling…</span>
                </>
              ) : (
                <>
                  <span>⚡</span> Auto-Enroll This Device
                </>
              )}
            </button>

            <button
              onClick={() => loadDevices(true)}
              disabled={loading}
              className="btn-ghost text-xs"
              style={{ opacity: loading ? 0.5 : 1 }}
            >
              ↻ Refresh
            </button>

            {devices.length > 0 && (
              <button
                type="button"
                onClick={handleSelectAllDevices}
                className="px-2.5 py-1.5 rounded-lg text-xs font-semibold text-slate-300 hover:text-white transition-colors border border-slate-700 bg-slate-900/60"
              >
                {selectedDeviceIds.length === devices.length ? "Deselect All" : "Select All"}
              </button>
            )}
          </div>
        </div>

        <div className="p-6 animate-fade-up space-y-5">
          {/* Bulk Selection Action Bar */}
          {selectedDeviceIds.length > 0 && (
            <div
              className="px-4 py-3 rounded-xl flex flex-wrap items-center justify-between gap-4 animate-fade-in shadow-xl"
              style={{
                background: "linear-gradient(135deg, rgba(239,68,68,0.15), rgba(15,23,41,0.95))",
                border: "1px solid rgba(239,68,68,0.4)",
              }}
            >
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={selectedDeviceIds.length === devices.length && devices.length > 0}
                  onChange={handleSelectAllDevices}
                  className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-cyan-500 cursor-pointer accent-cyan-500"
                />
                <span className="text-sm font-bold text-white">
                  {selectedDeviceIds.length} of {devices.length} device(s) selected
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleBulkDeactivateDevices}
                  disabled={bulkDeleting}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold text-amber-300 bg-amber-950/40 hover:bg-amber-900/60 border border-amber-500/30 transition-all disabled:opacity-50"
                >
                  ⏸️ Deactivate Selected
                </button>

                <button
                  type="button"
                  onClick={handleBulkDeleteDevices}
                  disabled={bulkDeleting}
                  className="px-4 py-1.5 rounded-lg text-xs font-bold text-white bg-red-600 hover:bg-red-500 transition-all shadow-md active:scale-95 disabled:opacity-50 flex items-center gap-1.5"
                >
                  {bulkDeleting ? (
                    <>
                      <span className="w-3.5 h-3.5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                      <span>Removing...</span>
                    </>
                  ) : (
                    <>
                      <span>🗑️</span>
                      <span>Remove Selected ({selectedDeviceIds.length})</span>
                    </>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => setSelectedDeviceIds([])}
                  className="text-xs text-slate-400 hover:text-white px-2 py-1"
                >
                  Clear Selection
                </button>
              </div>
            </div>
          )}

          {/* Error Banner */}
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
              <button className="btn-ghost text-xs" onClick={() => loadDevices(true)}>
                Retry
              </button>
            </div>
          )}

          {/* Dynamic Statistics Bar */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
            {[
              { label: "Total Devices", value: devices.length, color: "#00d4ff" },
              { label: "Active Agents", value: activeCount, color: "#34d058" },
              { label: "Windows", value: winCount, color: "#60a5fa" },
              { label: "Linux", value: linuxCount, color: "#ff9f0a" },
              { label: "macOS", value: macCount, color: "#a78bfa" },
              { label: "Android", value: androidCount, color: "#34d058" },
              { label: "iOS", value: iosCount, color: "#38bdf8" },
            ].map((s) => (
              <div
                key={s.label}
                className="rounded-xl py-3 px-3 text-center transition-all hover:border-cyan-500/30"
                style={{ background: "#0f1729", border: "1px solid #1a2744" }}
              >
                <p className="text-xl font-bold" style={{ color: s.color }}>
                  {s.value}
                </p>
                <p className="text-[10px] mt-0.5 uppercase tracking-wide" style={{ color: "#475569" }}>
                  {s.label}
                </p>
              </div>
            ))}
          </div>

          {/* Device Grid / Cards */}
          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <div
                  key={i}
                  className="rounded-xl p-5 animate-pulse"
                  style={{ background: "#0f1729", border: "1px solid #1a2744" }}
                >
                  <div className="flex items-start gap-3 mb-4">
                    <div className="w-10 h-10 rounded-lg animate-pulse" style={{ background: "rgba(26,39,68,0.8)" }} />
                    <div className="flex-1 space-y-2">
                      <div className="h-3 w-24 rounded animate-pulse" style={{ background: "rgba(26,39,68,0.8)" }} />
                      <div className="h-2 w-16 rounded animate-pulse" style={{ background: "rgba(26,39,68,0.8)" }} />
                    </div>
                  </div>
                  <div className="space-y-2">
                    {Array.from({ length: 4 }).map((_, j) => (
                      <div key={j} className="h-3 w-full rounded animate-pulse" style={{ background: "rgba(26,39,68,0.8)" }} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : devices.length === 0 ? (
            <div
              className="flex flex-col items-center justify-center py-20 px-4 gap-4 rounded-xl text-center"
              style={{ background: "#0f1729", border: "1px solid #1a2744" }}
            >
              <div
                className="w-16 h-16 rounded-2xl flex items-center justify-center text-4xl mb-1 shadow-inner"
                style={{ background: "rgba(0,212,255,0.05)", border: "1px solid rgba(0,212,255,0.15)" }}
              >
                🖥️
              </div>
              <div>
                <h3 className="text-base font-bold text-white">No devices enrolled</h3>
                <p className="text-xs text-slate-400 mt-1 max-w-sm">
                  Connect a DataGhost agent to start monitoring endpoints across your organization.
                </p>
              </div>
              <button
                onClick={() => setShowAddModal(true)}
                className="px-5 py-2 rounded-lg text-xs font-semibold text-white transition-all shadow-md hover:brightness-110 active:scale-95"
                style={{
                  background: "linear-gradient(135deg, #0089b2, #00d4ff)",
                  border: "1px solid rgba(0,212,255,0.4)",
                }}
              >
                + Add Device
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {devices.map((device) => {
                const devId = device.device_id || String(device.id);
                const isSelected = isDeviceSelected(devId);
                const isActive = device.status === "ACTIVE";
                const isOffline = device.status === "OFFLINE";
                const isDisabled = device.status === "DISABLED";
                const plat = device.platform || device.os_type || "Windows";

                let statusColor = "#34d058";
                if (isOffline) statusColor = "#ff3b3b";
                if (isDisabled) statusColor = "#64748b";

                return (
                  <div
                    key={devId}
                    onClick={() => handleDeviceClick(device)}
                    className="rounded-xl p-5 transition-all duration-200 hover:-translate-y-1 hover:border-cyan-500/40 cursor-pointer group shadow-lg"
                    style={{
                      background: isSelected ? "rgba(0,212,255,0.04)" : "#0f1729",
                      border: isSelected
                        ? "1px solid #00d4ff"
                        : `1px solid ${isActive ? "rgba(52,208,88,0.2)" : isOffline ? "rgba(255,59,59,0.2)" : "#1a2744"}`,
                      boxShadow: isSelected ? "0 0 15px rgba(0,212,255,0.15)" : "none",
                    }}
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-center gap-2.5">
                        <div
                          onClick={(e) => toggleSelectDevice(e, devId)}
                          className="p-1 rounded-md hover:bg-slate-800 transition-colors flex items-center justify-center cursor-pointer"
                          title={isSelected ? "Deselect device" : "Select device"}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => {}}
                            className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-cyan-500 cursor-pointer accent-cyan-500"
                          />
                        </div>
                        <div
                          className="w-10 h-10 rounded-lg flex items-center justify-center text-xl transition-transform group-hover:scale-110"
                          style={{ background: "rgba(26,39,68,0.7)", border: "1px solid #1a2744" }}
                        >
                          {getPlatformIcon(device.platform, device.os_type)}
                        </div>
                        <div>
                          <p className="text-sm font-bold text-white group-hover:text-cyan-400 transition-colors">
                            {device.device_name}
                          </p>
                          <p className="font-mono text-[10px] text-slate-400">
                            {device.device_id || `DG-DEV-${device.id}`}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full" style={{ background: `${statusColor}15`, border: `1px solid ${statusColor}30` }}>
                        <span
                          className="w-2 h-2 rounded-full"
                          style={{
                            background: statusColor,
                            boxShadow: isActive ? `0 0 6px ${statusColor}` : "none",
                            animation: isActive ? "pulse 2s ease-in-out infinite" : "none",
                          }}
                        />
                        <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: statusColor }}>
                          {device.status}
                        </span>
                      </div>
                    </div>

                    <div className="space-y-2 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Platform</span>
                        <PlatformBadge platform={plat} />
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">OS Version</span>
                        <span className="text-slate-200 font-medium truncate max-w-[150px]">
                          {device.os_version || device.os_name || plat}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">IP Address</span>
                        <span className="font-mono text-slate-300">{device.ip_address || "127.0.0.1"}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Last Seen</span>
                        <span className="text-slate-300">{timeAgo(device.last_seen)}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Agent</span>
                        <span
                          className="font-mono text-[11px] px-2 py-0.5 rounded"
                          style={{ background: "rgba(0,212,255,0.08)", color: "#00d4ff", border: "1px solid rgba(0,212,255,0.15)" }}
                        >
                          v{device.agent_version || "1.0.0"}
                        </span>
                      </div>
                    </div>

                    <div className="mt-4 pt-3 grid grid-cols-2 gap-2 border-t" style={{ borderColor: "#1a2744" }}>
                      <div className="text-center">
                        <p className="text-sm font-bold" style={{ color: "#00d4ff" }}>
                          {(device.files_scanned || 0).toLocaleString()}
                        </p>
                        <p className="text-[10px] text-slate-500 uppercase tracking-wider">Files Scanned</p>
                      </div>
                      <div className="text-center">
                        <p
                          className="text-sm font-bold"
                          style={{ color: (device.incidents_count || 0) > 0 ? "#ff9f0a" : "#34d058" }}
                        >
                          {device.incidents_count || 0}
                        </p>
                        <p className="text-[10px] text-slate-500 uppercase tracking-wider">Incidents</p>
                      </div>
                    </div>

                    {/* Quick Actions Bar */}
                    <div className="mt-3 pt-3 flex items-center justify-between gap-2 border-t border-slate-800">
                      {/* 1. Scan Device */}
                      <button
                        type="button"
                        onClick={(e) => handleQuickScan(e, device)}
                        disabled={scanLoadingDevice === (device.device_id || String(device.id))}
                        className="flex-1 py-1.5 px-2.5 rounded-lg text-xs font-semibold text-cyan-300 hover:text-white bg-cyan-950/40 hover:bg-cyan-900/60 border border-cyan-500/30 flex items-center justify-center gap-1.5 transition-all disabled:opacity-50"
                        title="Run DLP scan on this endpoint and get all security information"
                      >
                        {scanLoadingDevice === (device.device_id || String(device.id)) ? (
                          <>
                            <span className="w-3 h-3 border-2 border-cyan-400/20 border-t-cyan-400 rounded-full animate-spin" />
                            <span>Scanning…</span>
                          </>
                        ) : (
                          <>
                            <span>🔍</span>
                            <span>Scan</span>
                          </>
                        )}
                      </button>

                      {/* 2. Deactivate / Activate Device */}
                      <button
                        type="button"
                        onClick={(e) => handleQuickToggle(e, device)}
                        className="py-1.5 px-3 rounded-lg text-xs font-semibold transition-all border flex items-center gap-1"
                        style={{
                          background: isDisabled ? "rgba(52,208,88,0.1)" : "rgba(245,158,11,0.1)",
                          color: isDisabled ? "#34d058" : "#f59e0b",
                          borderColor: isDisabled ? "rgba(52,208,88,0.3)" : "rgba(245,158,11,0.3)",
                        }}
                        title={isDisabled ? "Re-activate device" : "Deactivate device"}
                      >
                        <span>{isDisabled ? "▶" : "⏸"}</span>
                        <span>{isDisabled ? "Activate" : "Deactivate"}</span>
                      </button>

                      {/* 3. Remove Device */}
                      <button
                        type="button"
                        onClick={(e) => handleQuickDelete(e, device)}
                        className="py-1.5 px-2.5 rounded-lg text-xs font-semibold text-red-400 hover:text-red-300 bg-red-950/30 hover:bg-red-900/50 border border-red-500/30 transition-all flex items-center justify-center"
                        title="Remove / delete device"
                      >
                        🗑️
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>

      {/* ─── MODAL 1: ADD NEW DEVICE & ENROLLMENT ──────────────────────────────── */}
      {showAddModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(3,7,18,0.85)", backdropFilter: "blur(8px)" }}
        >
          <div
            className="w-full max-w-lg rounded-2xl p-6 shadow-2xl animate-fade-up relative overflow-hidden"
            style={{ background: "#0d1526", border: "1px solid #1a2744" }}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                <span className="text-xl">
                  {enrollmentData ? getPlatformIcon(enrollmentData.platform) : "📱"}
                </span>
                <h2 className="text-base font-bold text-white">
                  {enrollmentData
                    ? `Enroll ${enrollmentData.platform} Device`
                    : showAndroidModeStep
                    ? "Android Enterprise Provisioning"
                    : showAndroidEnrollTypeStep
                    ? "Android Enrollment Method"
                    : "Add New Device"}
                </h2>
              </div>
              <button
                onClick={closeAddModal}
                className="text-slate-400 hover:text-white text-lg font-bold px-2 py-0.5 rounded"
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div className="py-5 space-y-5">
              {showPlatformStep && (
                /* Step 1: Select Platform */
                <div className="space-y-4">
                  <p className="text-xs text-slate-300">
                    Select the target operating system for the endpoint device you wish to enroll into DataGhost DLP.
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    {PLATFORMS.map((p) => {
                      const isSelected = selectedPlatform === p.id;
                      return (
                        <button
                          key={p.id}
                          type="button"
                          onClick={() => setSelectedPlatform(p.id)}
                          className="flex items-start gap-3 p-3 rounded-xl border text-left transition-all"
                          style={{
                            background: isSelected ? "rgba(0,212,255,0.08)" : "rgba(15,23,41,0.6)",
                            borderColor: isSelected ? "#00d4ff" : "#1a2744",
                          }}
                        >
                          <span className="text-2xl">{p.icon}</span>
                          <div>
                            <p className="text-xs font-bold" style={{ color: isSelected ? "#00d4ff" : "#ffffff" }}>
                              {p.label}
                            </p>
                            <p className="text-[10px] text-slate-400 mt-0.5">{p.desc}</p>
                          </div>
                        </button>
                      );
                    })}
                  </div>

                  <div className="pt-3 flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={closeAddModal}
                      className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        if (selectedPlatform === "Android") {
                          setAndroidEnrollType("easy");
                          setAddModalStep("android_type");
                        } else {
                          handleGenerateEnrollment("standard");
                        }
                      }}
                      disabled={generatingCode}
                      className="px-5 py-2 rounded-lg text-xs font-semibold text-white transition-all shadow-md hover:brightness-110 active:scale-95 disabled:opacity-50"
                      style={{ background: "linear-gradient(135deg, #0089b2, #00d4ff)" }}
                    >
                      {generatingCode
                        ? "Generating Token..."
                        : selectedPlatform === "Android"
                        ? "Next: Choose Enrollment Method →"
                        : "Generate Enrollment"}
                    </button>
                  </div>
                </div>
              )}

              {/* ── Step 2a: Android Enrollment Type (Automatic PRIMARY, Easy FALLBACK) ────── */}
              {showAndroidEnrollTypeStep && (
                <div className="space-y-4">
                  <div
                    className="flex items-start gap-3 p-3 rounded-xl"
                    style={{ background: "rgba(0,212,255,0.08)", border: "1px solid rgba(0,212,255,0.25)" }}
                  >
                    <span className="text-2xl flex-shrink-0 mt-0.5">⚡</span>
                    <div>
                      <p className="text-xs font-bold text-cyan-300">Choose Android Enrollment Method</p>
                      <p className="text-[11px] text-slate-300 mt-1">
                        Automatic Android Enterprise is recommended. Easy Enrollment is for existing/already-configured devices.
                      </p>
                    </div>
                  </div>

                  <div className="space-y-2.5">
                    {/* AUTOMATIC ANDROID ENTERPRISE (PRIMARY - FIRST) */}
                    <button
                      type="button"
                      onClick={() => setAndroidEnrollType("enterprise")}
                      className="w-full flex items-start gap-3 p-4 rounded-xl border text-left transition-all group ring-2"
                      style={{
                        background: androidEnrollType === "enterprise" ? "rgba(0,212,255,0.15)" : "rgba(0,212,255,0.04)",
                        borderColor: androidEnrollType === "enterprise" ? "#00d4ff" : "#00d4ff",
                        outlineOffset: androidEnrollType === "enterprise" ? "2px" : "0",
                        outlineStyle: androidEnrollType === "enterprise" ? "solid" : "none",
                        outlineColor: androidEnrollType === "enterprise" ? "rgba(0,212,255,0.3)" : "transparent",
                      }}
                    >
                      <div
                        className="w-10 h-10 rounded-lg flex items-center justify-center text-xl flex-shrink-0"
                        style={{ background: "rgba(0,212,255,0.15)", border: "2px solid #00d4ff" }}
                      >
                        ⚡
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <p className="text-xs font-bold" style={{ color: androidEnrollType === "enterprise" ? "#00d4ff" : "#ffffff" }}>
                            Automatic Android Enrollment
                          </p>
                          <span
                            className="text-[9px] px-2 py-0.5 rounded font-semibold"
                            style={{ background: "linear-gradient(135deg, rgba(0,212,255,0.2), rgba(0,212,255,0.1))", color: "#00d4ff", border: "1px solid rgba(0,212,255,0.4)", boxShadow: "0 0 8px rgba(0,212,255,0.2)" }}
                          >
                            🌟 RECOMMENDED
                          </span>
                        </div>
                        <p className="text-[10px] text-slate-300 leading-relaxed font-medium">
                          Official Android Enterprise provisioning. Automatic Device Owner setup via Android Setup Wizard. No manual APK download or installation needed.
                        </p>
                        <div className="mt-2.5 flex flex-wrap gap-1.5">
                          {["Automatic DPC install", "No manual download", "Official Android provisioning", "Fully Managed Device Owner"].map((tag) => (
                            <span key={tag} className="text-[9px] px-2 py-1 rounded font-semibold" style={{ background: "rgba(0,212,255,0.12)", border: "1px solid rgba(0,212,255,0.25)", color: "#00d4ff" }}>
                              {tag}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div
                        className="w-5 h-5 rounded-full border-2 flex-shrink-0 mt-1 transition-all flex items-center justify-center"
                        style={{
                          borderColor: androidEnrollType === "enterprise" ? "#00d4ff" : "#1a2744",
                          background: androidEnrollType === "enterprise" ? "#00d4ff" : "transparent",
                        }}
                      >
                        {androidEnrollType === "enterprise" && <span className="text-white text-[10px] font-bold">✓</span>}
                      </div>
                    </button>

                    {/* EASY / AGENT ENROLLMENT (SECONDARY - FALLBACK) */}
                    <button
                      type="button"
                      onClick={() => setAndroidEnrollType("easy")}
                      className="w-full flex items-start gap-3 p-4 rounded-xl border text-left transition-all group"
                      style={{
                        background: androidEnrollType === "easy" ? "rgba(52,208,88,0.08)" : "rgba(15,23,41,0.6)",
                        borderColor: androidEnrollType === "easy" ? "#34d058" : "#1a2744",
                      }}
                    >
                      <div
                        className="w-10 h-10 rounded-lg flex items-center justify-center text-xl flex-shrink-0"
                        style={{ background: "rgba(52,208,88,0.1)", border: "1px solid rgba(52,208,88,0.2)" }}
                      >
                        📱
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <p className="text-xs font-bold" style={{ color: androidEnrollType === "easy" ? "#34d058" : "#ffffff" }}>
                            Agent Enrollment (BYOD)
                          </p>
                          <span
                            className="text-[9px] px-1.5 py-0.5 rounded font-semibold"
                            style={{ background: "rgba(52,208,88,0.1)", color: "#34d058", border: "1px solid rgba(52,208,88,0.2)" }}
                          >
                            For Existing Devices
                          </span>
                        </div>
                        <p className="text-[10px] text-slate-400 leading-relaxed">
                          For already-configured personal or BYOD Android phones. Download & install the DataGhost Agent app, then enroll. No factory reset needed.
                        </p>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {["No factory reset", "Manual APK install", "Agent-managed mode", "Existing phones"].map((tag) => (
                            <span key={tag} className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: "rgba(15,23,41,0.8)", border: "1px solid #1a2744", color: "#64748b" }}>
                              {tag}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div
                        className="w-4 h-4 rounded-full border-2 flex-shrink-0 mt-1 transition-all"
                        style={{
                          borderColor: androidEnrollType === "easy" ? "#34d058" : "#1a2744",
                          background: androidEnrollType === "easy" ? "#34d058" : "transparent",
                        }}
                      />
                    </button>
                  </div>

                  <div className="pt-2 flex justify-between items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setAddModalStep("platform")}
                      className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800"
                    >
                      ← Back
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        if (androidEnrollType === "easy") {
                          handleGenerateEnrollment("easy");
                        } else if (androidEnrollType === "enterprise") {
                          setAddModalStep("android_enterprise");
                        }
                      }}
                      disabled={generatingCode || !androidEnrollType}
                      className="px-5 py-2 rounded-lg text-xs font-semibold text-white transition-all shadow-md hover:brightness-110 active:scale-95 disabled:opacity-50"
                      style={{
                        background: !androidEnrollType
                          ? "#1a2744"
                          : androidEnrollType === "easy"
                          ? "linear-gradient(135deg, #16a34a, #34d058)"
                          : "linear-gradient(135deg, #0089b2, #00d4ff)",
                      }}
                    >
                      {generatingCode
                        ? "Generating..."
                        : androidEnrollType === "enterprise"
                        ? "Next: Select Device Type →"
                        : "Generate Agent Enrollment QR →"}
                    </button>
                  </div>
                </div>
              )}

              {/* ── Step 2b: Android Enterprise Device Type (Fully Managed RECOMMENDED) ──────────── */}
              {showAndroidModeStep && (
                <div className="space-y-4">
                  <div
                    className="flex items-start gap-3 p-3 rounded-xl"
                    style={{ background: "rgba(0,212,255,0.08)", border: "1px solid rgba(0,212,255,0.25)" }}
                  >
                    <span className="text-2xl flex-shrink-0 mt-0.5">🏢</span>
                    <div>
                      <p className="text-xs font-bold text-cyan-300">Select Device Type</p>
                      <p className="text-[11px] text-slate-300 mt-1">
                        Choose whether this is a corporate-owned device or a personal BYOD device. Most corporate deployments use Fully Managed (Device Owner).
                      </p>
                    </div>
                  </div>

                  <div className="space-y-2.5">
                    {/* Fully Managed (DEVICE OWNER - PRIMARY RECOMMENDED) */}
                    <button
                      type="button"
                      onClick={() => setAndroidMode("fully_managed")}
                      className="w-full flex items-start gap-3 p-4 rounded-xl border text-left transition-all group ring-2"
                      style={{
                        background: androidMode === "fully_managed" ? "rgba(167,139,250,0.12)" : "rgba(167,139,250,0.04)",
                        borderColor: androidMode === "fully_managed" ? "#a78bfa" : "#a78bfa",
                        outlineOffset: androidMode === "fully_managed" ? "2px" : "0",
                        outlineStyle: androidMode === "fully_managed" ? "solid" : "none",
                        outlineColor: androidMode === "fully_managed" ? "rgba(167,139,250,0.3)" : "transparent",
                      }}
                    >
                      <div
                        className="w-10 h-10 rounded-lg flex items-center justify-center text-xl flex-shrink-0"
                        style={{ background: "rgba(167,139,250,0.15)", border: "2px solid #a78bfa" }}
                      >
                        🔒
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <p className="text-xs font-bold" style={{ color: androidMode === "fully_managed" ? "#a78bfa" : "#ffffff" }}>
                            Fully Managed (Device Owner)
                          </p>
                          <span
                            className="text-[9px] px-2 py-0.5 rounded font-semibold"
                            style={{ background: "linear-gradient(135deg, rgba(167,139,250,0.2), rgba(167,139,250,0.1))", color: "#a78bfa", border: "1px solid rgba(167,139,250,0.4)", boxShadow: "0 0 8px rgba(167,139,250,0.2)" }}
                          >
                            🌟 RECOMMENDED
                          </span>
                        </div>
                        <p className="text-[10px] text-slate-300 leading-relaxed font-medium">
                          Company-owned device. Full device management via Android Device Owner mode. Requires factory reset. Automatic DPC installation during setup wizard.
                        </p>
                        <div className="mt-2.5 flex flex-wrap gap-1.5">
                          {["Device Owner mode", "Full management", "Corporate-owned", "Factory reset required"].map((tag) => (
                            <span key={tag} className="text-[9px] px-2 py-1 rounded font-semibold" style={{ background: "rgba(167,139,250,0.12)", border: "1px solid rgba(167,139,250,0.25)", color: "#a78bfa" }}>
                              {tag}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div
                        className="w-5 h-5 rounded-full border-2 flex-shrink-0 mt-1 transition-all flex items-center justify-center"
                        style={{
                          borderColor: androidMode === "fully_managed" ? "#a78bfa" : "#1a2744",
                          background: androidMode === "fully_managed" ? "#a78bfa" : "transparent",
                        }}
                      >
                        {androidMode === "fully_managed" && <span className="text-white text-[10px] font-bold">✓</span>}
                      </div>
                    </button>

                    {/* Work Profile (BYOD - SECONDARY) */}
                    <button
                      type="button"
                      onClick={() => setAndroidMode("work_profile")}
                      className="w-full flex items-start gap-3 p-4 rounded-xl border text-left transition-all group"
                      style={{
                        background: androidMode === "work_profile" ? "rgba(0,212,255,0.08)" : "rgba(15,23,41,0.6)",
                        borderColor: androidMode === "work_profile" ? "#00d4ff" : "#1a2744",
                      }}
                    >
                      <div
                        className="w-10 h-10 rounded-lg flex items-center justify-center text-xl flex-shrink-0"
                        style={{ background: "rgba(0,212,255,0.1)", border: "1px solid rgba(0,212,255,0.2)" }}
                      >
                        🏢
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <p className="text-xs font-bold" style={{ color: androidMode === "work_profile" ? "#00d4ff" : "#ffffff" }}>
                            Work Profile (BYOD)
                          </p>
                          <span
                            className="text-[9px] px-1.5 py-0.5 rounded font-semibold"
                            style={{ background: "rgba(0,212,255,0.1)", color: "#00d4ff", border: "1px solid rgba(0,212,255,0.2)" }}
                          >
                            Personal Device
                          </span>
                        </div>
                        <p className="text-[10px] text-slate-400 leading-relaxed">
                          Employee-owned personal device. A separate managed work profile is created within the device. Personal data remains private.
                        </p>
                        <p className="text-[10px] text-amber-400 mt-1.5 font-semibold">
                          ⚠ Requires DataGhost Agent app to be installed on the device first.
                        </p>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {["Profile Owner", "BYOD / Personal", "Work profile created", "App install required"].map((tag) => (
                            <span key={tag} className="text-[9px] px-1.5 py-0.5 rounded" style={{ background: "rgba(15,23,41,0.8)", border: "1px solid #1a2744", color: "#64748b" }}>
                              {tag}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div
                        className="w-4 h-4 rounded-full border-2 flex-shrink-0 mt-1 transition-all"
                        style={{
                          borderColor: androidMode === "work_profile" ? "#00d4ff" : "#1a2744",
                          background: androidMode === "work_profile" ? "#00d4ff" : "transparent",
                        }}
                      />
                    </button>
                  </div>

                  <div className="pt-2 flex justify-between items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setAddModalStep("android_type")}
                      className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800"
                    >
                      ← Back
                    </button>
                    <button
                      type="button"
                      onClick={() => handleGenerateEnrollment("enterprise")}
                      disabled={generatingCode || !androidMode}
                      className="px-5 py-2 rounded-lg text-xs font-semibold text-white transition-all shadow-md hover:brightness-110 active:scale-95 disabled:opacity-50"
                      style={{
                        background: !androidMode
                          ? "#1a2744"
                          : androidMode === "fully_managed"
                          ? "linear-gradient(135deg, #7c3aed, #a78bfa)"
                          : "linear-gradient(135deg, #0089b2, #00d4ff)",
                      }}
                    >
                      {generatingCode ? "Generating..." : "Generate Enterprise QR Code →"}
                    </button>
                  </div>
                </div>
              )}

              {/* ── Step 3: QR Code & Enrollment Code Display ─────────────────── */}
              {enrollmentData && (
                <div className="flex flex-col items-center text-center space-y-4">
                  {/* Status Banner */}
                  {enrollmentStatus === "USED" ? (
                    <div
                      className="w-full py-3 px-4 rounded-xl text-center space-y-1"
                      style={{ background: "rgba(52,208,88,0.1)", border: "1px solid rgba(52,208,88,0.3)", color: "#34d058" }}
                    >
                      <p className="text-sm font-bold">🎉 Enrollment Successful!</p>
                      <p className="text-xs text-slate-300">
                        Device registered as <strong className="text-white">{enrolledDeviceName}</strong>
                      </p>
                    </div>
                  ) : enrollmentStatus === "EXPIRED" ? (
                    <div
                      className="w-full py-3 px-4 rounded-xl text-center space-y-1"
                      style={{ background: "rgba(255,59,59,0.1)", border: "1px solid rgba(255,59,59,0.3)", color: "#ff3b3b" }}
                    >
                      <p className="text-sm font-bold">⏱️ Enrollment Code Expired</p>
                      <p className="text-xs text-slate-300">Generate a new enrollment code to continue.</p>
                    </div>
                  ) : (
                    /* Instructions based on platform and mode */
                    enrollmentData.platform === "Android" ? (
                      <div
                        className="w-full px-4 py-3 rounded-xl text-left space-y-2"
                        style={{ background: "rgba(52,208,88,0.05)", border: "1px solid rgba(52,208,88,0.2)" }}
                      >
                        <p className="text-[11px] font-bold text-green-400 uppercase tracking-wider">
                          {androidEnrollType === "easy"
                            ? "⚡ Easy Android Setup — Scan with Camera or Visit Link"
                            : androidMode === "fully_managed"
                            ? "🔒 Fully Managed — Scan During Android Setup Wizard"
                            : "🏢 Work Profile — Scan with DataGhost Agent App"}
                        </p>
                        {androidEnrollType === "easy" ? (
                          <ol className="text-[11px] text-slate-300 space-y-1 list-none">
                            <li>1. Scan the QR code below with your <strong className="text-white">regular Phone Camera</strong> or open the link in Chrome</li>
                            <li>2. Tap <strong className="text-white">&quot;Download &amp; Install Agent&quot;</strong> on the portal page</li>
                            <li>3. Open the app — it will automatically enroll and activate background DLP monitoring</li>
                          </ol>
                        ) : androidMode === "fully_managed" ? (
                          <ol className="text-[11px] text-slate-300 space-y-1 list-none">
                            <li>1. Factory reset the corporate Android device</li>
                            <li>2. On the setup wizard, tap the screen <strong className="text-white">6 times</strong> quickly</li>
                            <li>3. Select <strong className="text-white">&quot;Set up with QR code&quot;</strong> and scan the QR code</li>
                            <li>4. <strong className="text-amber-400">Complete Android&apos;s provisioning and management consent screens</strong></li>
                            <li>5. After approval, the device registers in your dashboard</li>
                          </ol>
                        ) : (
                          <ol className="text-[11px] text-slate-300 space-y-1 list-none">
                            <li>1. Install the <strong className="text-white">DataGhost Agent</strong> app on the Android device</li>
                            <li>2. Open the app → tap <strong className="text-white">&quot;Enroll Device&quot;</strong></li>
                            <li>3. Scan the QR code below or enter the enrollment code manually</li>
                            <li>4. Accept the Work Profile setup when prompted</li>
                          </ol>
                        )}
                      </div>
                    ) : (
                      <p className="text-xs text-slate-300">
                        Scan the QR code with the DataGhost app or open the web link on the endpoint device.
                      </p>
                    )
                  )}

                  {/* QR Code Container */}
                  {enrollmentStatus === "PENDING" && (
                    <div
                      className="p-3 rounded-2xl shadow-inner relative flex flex-col items-center"
                      style={{ background: "#090f1d", border: "1px solid #1a2744" }}
                    >
                      {qrDataUrl ? (
                        <img
                          src={qrDataUrl}
                          alt="Enrollment QR Code"
                          className="w-48 h-48 rounded-xl shadow-lg"
                        />
                      ) : (
                        <div className="w-48 h-48 flex items-center justify-center text-slate-500 text-xs">
                          Generating QR Code...
                        </div>
                      )}

                      <div className="flex items-center gap-2 mt-3">
                        <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                        <span className="text-[11px] font-semibold text-cyan-400">
                          Waiting for device...
                        </span>
                      </div>

                      <button
                        type="button"
                        onClick={handleAutoEnrollCurrentModal}
                        disabled={modalAutoEnrolling}
                        className="mt-3 w-full py-2 px-3 rounded-xl text-xs font-semibold text-white flex items-center justify-center gap-1.5 transition-all shadow-md hover:brightness-110 active:scale-95 disabled:opacity-50"
                        style={{
                          background: "linear-gradient(135deg, #0089b2, #00d4ff)",
                          border: "1px solid rgba(0,212,255,0.4)",
                        }}
                      >
                        {modalAutoEnrolling ? (
                          <>
                            <span className="w-3 h-3 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                            <span>Auto-Enrolling Device…</span>
                          </>
                        ) : (
                          <>
                            <span>⚡</span>
                            <span>Auto-Enroll This Device (1-Click)</span>
                          </>
                        )}
                      </button>
                    </div>
                  )}

                  {/* Enrollment Code Display */}
                  <div className="w-full space-y-1">
                    <p className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">
                      Enrollment Code
                    </p>
                    <div
                      className="flex items-center justify-between px-4 py-2.5 rounded-xl font-mono text-base font-bold text-white"
                      style={{ background: "rgba(0,212,255,0.06)", border: "1px solid rgba(0,212,255,0.2)" }}
                    >
                      <span className="tracking-widest text-cyan-400">
                        {enrollmentData.enrollment_code}
                      </span>
                      <button
                        type="button"
                        onClick={() => handleCopyCode(enrollmentData.enrollment_code)}
                        className="text-xs text-slate-400 hover:text-white px-2 py-1 rounded bg-slate-800"
                      >
                        {copySuccess ? "✔ Copied" : "Copy"}
                      </button>
                    </div>
                  </div>

                  {/* Universal Web Link */}
                  {enrollmentStatus === "PENDING" && (
                    <div className="w-full space-y-1">
                      <p className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">
                        Direct Enrollment Link
                      </p>
                      <div
                        className="flex items-center justify-between px-3 py-2 rounded-xl text-xs font-mono"
                        style={{ background: "rgba(15,23,41,0.6)", border: "1px solid #1a2744" }}
                      >
                        <span className="text-slate-300 truncate text-[11px]">
                          {typeof window !== "undefined"
                            ? `${window.location.origin}/enroll/${enrollmentData.enrollment_code}`
                            : `/enroll/${enrollmentData.enrollment_code}`}
                        </span>
                        <div className="flex items-center gap-1.5 ml-2 flex-shrink-0">
                          <button
                            type="button"
                            onClick={() => {
                              const url = typeof window !== "undefined"
                                ? `${window.location.origin}/enroll/${enrollmentData.enrollment_code}`
                                : "";
                              if (url) handleCopyUrl(url);
                            }}
                            className="text-xs text-slate-400 hover:text-white px-2 py-1 rounded bg-slate-800"
                          >
                            {copyUrlSuccess ? "✔ Copied" : "Copy Link"}
                          </button>
                          <a
                            href={`/enroll/${enrollmentData.enrollment_code}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-cyan-400 hover:underline px-2 py-1 rounded bg-slate-800"
                          >
                            Open ↗
                          </a>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Countdown Timer */}
                  {enrollmentStatus === "PENDING" && (
                    <div className="text-xs text-slate-400 flex items-center gap-1">
                      <span>Expires in:</span>
                      <span className="font-mono font-bold text-amber-400">
                        {String(Math.floor(timeLeft / 60)).padStart(2, "0")}:
                        {String(timeLeft % 60).padStart(2, "0")}
                      </span>
                    </div>
                  )}

                  {/* Footer Actions */}
                  <div className="pt-2 w-full flex justify-center gap-3">
                    {enrollmentStatus === "EXPIRED" ? (
                      <button
                        type="button"
                        onClick={() => handleGenerateEnrollment(androidEnrollType === "easy" ? "easy" : androidEnrollType === "enterprise" ? "enterprise" : "standard")}
                        className="px-5 py-2 rounded-lg text-xs font-semibold text-white transition-all shadow-md hover:brightness-110 active:scale-95"
                        style={{ background: "linear-gradient(135deg, #0089b2, #00d4ff)" }}
                      >
                        Generate New Code
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={closeAddModal}
                        className="px-6 py-2 rounded-lg text-xs font-semibold text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700"
                      >
                        {enrollmentStatus === "USED" ? "Done" : "Cancel"}
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ─── MODAL 2: DEVICE DETAILS & ACTIONS ───────────────────────────────── */}
      {selectedDevice && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 overflow-y-auto"
          style={{ background: "rgba(3,7,18,0.85)", backdropFilter: "blur(8px)" }}
        >
          <div
            className="w-full max-w-2xl rounded-2xl p-6 shadow-2xl animate-fade-up relative overflow-hidden my-8"
            style={{ background: "#0d1526", border: "1px solid #1a2744" }}
          >
            <div className="flex items-start justify-between pb-4 border-b border-slate-800">
              <div className="flex items-center gap-3">
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl shadow"
                  style={{ background: "rgba(26,39,68,0.8)", border: "1px solid #1a2744" }}
                >
                  {getPlatformIcon(selectedDevice.platform, selectedDevice.os_type)}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-base font-bold text-white">{selectedDevice.device_name}</h2>
                    <PlatformBadge platform={selectedDevice.platform || selectedDevice.os_type} />
                  </div>
                  <p className="font-mono text-xs text-slate-400 mt-0.5">
                    ID: {selectedDevice.device_id || `DG-DEV-${selectedDevice.id}`}
                  </p>
                </div>
              </div>

              <button
                onClick={() => {
                  setSelectedDevice(null);
                  setDeviceDetail(null);
                }}
                className="text-slate-400 hover:text-white text-lg font-bold px-2 py-0.5 rounded"
              >
                ✕
              </button>
            </div>

            {loadingDetail ? (
              <div className="py-12 flex justify-center items-center">
                <div className="spinner" />
              </div>
            ) : (
              <div className="py-5 space-y-6 max-h-[70vh] overflow-y-auto pr-1">
                {/* 1. Device Information */}
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-cyan-400 mb-3 flex items-center gap-1.5">
                    <span>💻</span> Device Information
                  </h3>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 p-4 rounded-xl text-xs" style={{ background: "rgba(15,23,41,0.7)", border: "1px solid #1a2744" }}>
                    <div>
                      <p className="text-slate-500 text-[10px] uppercase">Status</p>
                      <p className="font-semibold text-white">{selectedDevice.status}</p>
                    </div>
                    <div>
                      <p className="text-slate-500 text-[10px] uppercase">Platform</p>
                      <p className="font-semibold text-white">{deviceDetail?.platform || selectedDevice.platform || "Windows"}</p>
                    </div>
                    <div>
                      <p className="text-slate-500 text-[10px] uppercase">OS Version</p>
                      <p className="font-semibold text-white truncate">{deviceDetail?.os_version || deviceDetail?.os_name || "N/A"}</p>
                    </div>
                    <div>
                      <p className="text-slate-500 text-[10px] uppercase">IP Address</p>
                      <p className="font-mono text-slate-200">{selectedDevice.ip_address || "127.0.0.1"}</p>
                    </div>
                    <div>
                      <p className="text-slate-500 text-[10px] uppercase">Hostname</p>
                      <p className="font-mono text-slate-200 truncate">{deviceDetail?.hostname || selectedDevice.device_name}</p>
                    </div>
                    <div>
                      <p className="text-slate-500 text-[10px] uppercase">Agent Version</p>
                      <p className="font-mono text-cyan-400">v{selectedDevice.agent_version || "1.0.0"}</p>
                    </div>
                    <div>
                      <p className="text-slate-500 text-[10px] uppercase">Last Seen</p>
                      <p className="text-slate-200">{timeAgo(selectedDevice.last_seen)}</p>
                    </div>
                    <div>
                      <p className="text-slate-500 text-[10px] uppercase">Enrolled At</p>
                      <p className="text-slate-200">{formatDate(deviceDetail?.enrolled_at || selectedDevice.registered_at)}</p>
                    </div>
                    <div>
                      <p className="text-slate-500 text-[10px] uppercase">Architecture</p>
                      <p className="text-slate-200">{deviceDetail?.architecture || "x64"}</p>
                    </div>
                  </div>
                </div>

                {/* 2. Security Metrics */}
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-cyan-400 mb-3 flex items-center gap-1.5">
                    <span>🛡️</span> Security & Compliance
                  </h3>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3 rounded-xl text-center" style={{ background: "rgba(15,23,41,0.7)", border: "1px solid #1a2744" }}>
                      <p className="text-base font-bold text-cyan-400">{(selectedDevice.files_scanned || 0).toLocaleString()}</p>
                      <p className="text-[10px] text-slate-400 uppercase mt-0.5">Files Scanned</p>
                    </div>
                    <div className="p-3 rounded-xl text-center" style={{ background: "rgba(15,23,41,0.7)", border: "1px solid #1a2744" }}>
                      <p className="text-base font-bold" style={{ color: (selectedDevice.incidents_count || 0) > 0 ? "#ff9f0a" : "#34d058" }}>
                        {selectedDevice.incidents_count || 0}
                      </p>
                      <p className="text-[10px] text-slate-400 uppercase mt-0.5">Incidents</p>
                    </div>
                    <div className="p-3 rounded-xl text-center" style={{ background: "rgba(15,23,41,0.7)", border: "1px solid #1a2744" }}>
                      <p className="text-xs font-semibold text-slate-200">{timeAgo(deviceDetail?.last_scan)}</p>
                      <p className="text-[10px] text-slate-400 uppercase mt-0.5">Last Scan</p>
                    </div>
                    <div className="p-3 rounded-xl text-center" style={{ background: "rgba(15,23,41,0.7)", border: "1px solid #1a2744" }}>
                      <p className="text-xs font-semibold text-emerald-400">{deviceDetail?.policy_status || "Enforced"}</p>
                      <p className="text-[10px] text-slate-400 uppercase mt-0.5">Policy Status</p>
                    </div>
                  </div>
                </div>

                {/* 3. Activity / Recent Incidents */}
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-cyan-400 mb-3 flex items-center gap-1.5">
                    <span>⚡</span> Recent Device Incidents
                  </h3>
                  {deviceDetail?.recent_incidents && deviceDetail.recent_incidents.length > 0 ? (
                    <div className="rounded-xl overflow-hidden border border-slate-800 text-xs">
                      <table className="w-full text-left border-collapse">
                        <thead>
                          <tr className="bg-slate-900/80 text-slate-400 border-b border-slate-800 font-semibold text-[10px] uppercase">
                            <th className="p-2.5">Time</th>
                            <th className="p-2.5">File</th>
                            <th className="p-2.5">Severity</th>
                            <th className="p-2.5">Risk Score</th>
                            <th className="p-2.5">Action</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/50">
                          {deviceDetail.recent_incidents.map((inc) => (
                            <tr key={inc.incident_id} className="hover:bg-slate-800/40">
                              <td className="p-2.5 text-slate-400">{timeAgo(inc.timestamp)}</td>
                              <td className="p-2.5 font-mono text-white max-w-[140px] truncate">{inc.filename || "file.txt"}</td>
                              <td className="p-2.5 font-semibold" style={{ color: inc.severity === "CRITICAL" ? "#ff3b3b" : inc.severity === "HIGH" ? "#ff9f0a" : "#00d4ff" }}>
                                {inc.severity}
                              </td>
                              <td className="p-2.5 font-bold text-slate-200">{inc.risk_score}/100</td>
                              <td className="p-2.5 font-semibold text-slate-300">{inc.action_taken}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="p-4 rounded-xl text-center text-xs text-slate-500" style={{ background: "rgba(15,23,41,0.5)", border: "1px dashed #1a2744" }}>
                      No recent security incidents logged for this endpoint.
                    </div>
                  )}
                </div>

                {showDeleteConfirm && (
                  <div className="p-4 rounded-xl border border-red-500/30 bg-red-500/10 space-y-3">
                    <p className="text-xs font-bold text-red-400">
                      ⚠ Are you sure you want to remove endpoint device &apos;{selectedDevice.device_name}&apos;?
                    </p>
                    <p className="text-[11px] text-slate-300">
                      This action will unenroll the device from DataGhost. It can be re-enrolled later using a new code.
                    </p>
                    <div className="flex justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => setShowDeleteConfirm(false)}
                        className="px-3 py-1.5 rounded text-xs text-slate-300 bg-slate-800 hover:bg-slate-700"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={handleRemoveDevice}
                        disabled={actionLoading}
                        className="px-4 py-1.5 rounded text-xs font-bold text-white bg-red-600 hover:bg-red-500 disabled:opacity-50"
                      >
                        {actionLoading ? "Removing..." : "Confirm Remove"}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Modal Footer Actions */}
            <div className="pt-4 border-t border-slate-800 flex items-center justify-between">
              <button
                type="button"
                onClick={() => handleDeviceClick(selectedDevice)}
                disabled={loadingDetail}
                className="btn-ghost text-xs text-slate-400 hover:text-white"
              >
                ↻ Refresh
              </button>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={(e) => handleQuickScan(e, selectedDevice)}
                  disabled={scanLoadingDevice === (selectedDevice.device_id || String(selectedDevice.id))}
                  className="px-3.5 py-1.5 rounded-lg text-xs font-semibold text-cyan-300 hover:text-white bg-cyan-950/60 hover:bg-cyan-900 border border-cyan-500/40 flex items-center gap-1.5 transition-all disabled:opacity-50"
                >
                  {scanLoadingDevice === (selectedDevice.device_id || String(selectedDevice.id)) ? (
                    <>
                      <span className="w-3 h-3 border-2 border-cyan-400/20 border-t-cyan-400 rounded-full animate-spin" />
                      <span>Scanning Device…</span>
                    </>
                  ) : (
                    <>
                      <span>🔍</span>
                      <span>Scan Device</span>
                    </>
                  )}
                </button>

                <button
                  type="button"
                  onClick={handleToggleStatus}
                  disabled={actionLoading}
                  className="px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 disabled:opacity-50"
                >
                  {selectedDevice.status === "DISABLED" ? "Re-enable Device" : "Deactivate Device"}
                </button>

                {!showDeleteConfirm && (
                  <button
                    type="button"
                    onClick={() => setShowDeleteConfirm(true)}
                    className="px-3.5 py-1.5 rounded-lg text-xs font-semibold text-red-400 hover:text-red-300 bg-red-950/40 border border-red-500/20 hover:bg-red-900/40"
                  >
                    Remove Device
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ─── MODAL 3: DEVICE SCAN RESULTS & ALL INFORMATION ──────────────────── */}
      {scanResultData && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 overflow-y-auto"
          style={{ background: "rgba(3,7,18,0.85)", backdropFilter: "blur(8px)" }}
        >
          <div
            className="w-full max-w-2xl rounded-2xl p-6 shadow-2xl animate-fade-up relative overflow-hidden my-8"
            style={{ background: "#0d1526", border: "1px solid #1a2744" }}
          >
            {/* Modal Header */}
            <div className="flex items-start justify-between pb-4 border-b border-slate-800">
              <div className="flex items-center gap-3">
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl shadow"
                  style={{ background: "rgba(0,212,255,0.1)", border: "1px solid rgba(0,212,255,0.3)" }}
                >
                  🔍
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-base font-bold text-white">Endpoint Scan Summary</h2>
                    <span
                      className="text-[10px] font-bold px-2 py-0.5 rounded uppercase"
                      style={{ background: "rgba(52,208,88,0.15)", color: "#34d058", border: "1px solid rgba(52,208,88,0.3)" }}
                    >
                      Scan Complete
                    </span>
                  </div>
                  <p className="font-mono text-xs text-slate-400 mt-0.5">
                    Endpoint: <strong className="text-white">{scanResultData.device?.device_name}</strong> ({scanResultData.device?.device_id})
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setScanResultData(null)}
                className="text-slate-400 hover:text-white text-lg font-bold px-2 py-0.5 rounded"
              >
                ✕
              </button>
            </div>

            {/* Scan Metrics Overview */}
            <div className="py-5 space-y-5 max-h-[70vh] overflow-y-auto pr-1">
              {/* Device Info Bar */}
              {scanResultData.device && (
                <div
                  className="flex flex-wrap items-center gap-x-5 gap-y-1 px-4 py-2.5 rounded-xl text-[11px]"
                  style={{ background: "rgba(0,212,255,0.05)", border: "1px solid rgba(0,212,255,0.15)" }}
                >
                  {scanResultData.device.hostname && (
                    <span className="text-slate-400">Host: <strong className="text-cyan-300">{scanResultData.device.hostname}</strong></span>
                  )}
                  {scanResultData.device.ip_address && (
                    <span className="text-slate-400">IP: <strong className="text-cyan-300 font-mono">{scanResultData.device.ip_address}</strong></span>
                  )}
                  {scanResultData.device.platform && (
                    <span className="text-slate-400">Platform: <strong className="text-cyan-300">{scanResultData.device.platform}</strong></span>
                  )}
                  {scanResultData.device.os_name && (
                    <span className="text-slate-400">OS: <strong className="text-cyan-300">{scanResultData.device.os_name}</strong></span>
                  )}
                  {scanResultData.source && (
                    <span className="text-slate-400">Source: <strong className="text-cyan-300 uppercase">{scanResultData.source?.replace(/_/g, " ")}</strong></span>
                  )}
                </div>
              )}

              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                <div className="p-3 rounded-xl text-center" style={{ background: "rgba(15,23,41,0.7)", border: "1px solid #1a2744" }}>
                  <p className="text-xl font-bold text-cyan-400">{scanResultData.scanned_files_count || 0}</p>
                  <p className="text-[10px] text-slate-400 uppercase mt-0.5">Files Scanned</p>
                </div>
                <div className="p-3 rounded-xl text-center" style={{ background: "rgba(15,23,41,0.7)", border: "1px solid #1a2744" }}>
                  <p className="text-xl font-bold" style={{ color: scanResultData.threats_detected > 0 ? "#ff3b3b" : "#34d058" }}>
                    {scanResultData.threats_detected || 0}
                  </p>
                  <p className="text-[10px] text-slate-400 uppercase mt-0.5">Threats Detected</p>
                </div>
                <div className="p-3 rounded-xl text-center" style={{ background: "rgba(15,23,41,0.7)", border: "1px solid #1a2744" }}>
                  <p className="text-xl font-bold" style={{ color: (scanResultData.high_risk_count || 0) > 0 ? "#ff3b3b" : "#34d058" }}>
                    {scanResultData.high_risk_count || 0}
                  </p>
                  <p className="text-[10px] text-slate-400 uppercase mt-0.5">High Risk</p>
                </div>
                <div className="p-3 rounded-xl text-center" style={{ background: "rgba(15,23,41,0.7)", border: "1px solid #1a2744" }}>
                  <p className="text-xl font-bold text-amber-400">
                    {scanResultData.scan_results?.reduce((acc: number, r: any) => acc + (r.findings?.length || 0), 0) || 0}
                  </p>
                  <p className="text-[10px] text-slate-400 uppercase mt-0.5">DLP Findings</p>
                </div>
                <div className="p-3 rounded-xl text-center" style={{ background: "rgba(15,23,41,0.7)", border: "1px solid #1a2744" }}>
                  <p className="text-sm font-bold text-violet-400 mt-1">
                    {scanResultData.total_bytes_scanned
                      ? scanResultData.total_bytes_scanned > 1024 * 1024
                        ? `${(scanResultData.total_bytes_scanned / (1024 * 1024)).toFixed(1)} MB`
                        : scanResultData.total_bytes_scanned > 1024
                        ? `${(scanResultData.total_bytes_scanned / 1024).toFixed(1)} KB`
                        : `${scanResultData.total_bytes_scanned} B`
                      : "—"}
                  </p>
                  <p className="text-[10px] text-slate-400 uppercase mt-1.5">Data Scanned</p>
                </div>
              </div>

              {/* Scanned Files & Detailed Information */}
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-cyan-400 mb-3 flex items-center gap-1.5">
                  <span>📄</span> Scanned Files & Security Findings
                </h3>
                <div className="space-y-3">
                  {scanResultData.scan_results?.map((res: any, idx: number) => {
                    const isHigh = res.risk_score >= 70;
                    const isMed = res.risk_score >= 30 && res.risk_score < 70;
                    const badgeBg = isHigh ? "rgba(255,59,59,0.15)" : isMed ? "rgba(245,158,11,0.15)" : "rgba(52,208,88,0.15)";
                    const badgeColor = isHigh ? "#ff3b3b" : isMed ? "#f59e0b" : "#34d058";

                    return (
                      <div
                        key={idx}
                        className="p-3.5 rounded-xl space-y-2"
                        style={{ background: "rgba(15,23,41,0.7)", border: `1px solid ${isHigh ? "rgba(255,59,59,0.3)" : "#1a2744"}` }}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="text-base">{isHigh ? "🚨" : isMed ? "⚠️" : "✅"}</span>
                            <span className="font-mono text-xs font-bold text-white">{res.filename}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span
                              className="text-[10px] font-bold px-2 py-0.5 rounded uppercase"
                              style={{ background: badgeBg, color: badgeColor, border: `1px solid ${badgeColor}30` }}
                            >
                              {res.classification} ({res.risk_score}/100)
                            </span>
                            <span
                              className="text-[10px] font-bold px-2 py-0.5 rounded uppercase"
                              style={{
                                background: res.action_taken === "BLOCKED" ? "rgba(255,59,59,0.2)" : "rgba(0,212,255,0.15)",
                                color: res.action_taken === "BLOCKED" ? "#ff3b3b" : "#00d4ff",
                              }}
                            >
                              {res.action_taken}
                            </span>
                          </div>
                        </div>

                        {/* File metadata row */}
                        <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-[10px] text-slate-500 font-mono">
                          {res.file_hash && <span>SHA-256: {res.file_hash.slice(0, 16)}…</span>}
                          {res.file_size != null && res.file_size > 0 && (
                            <span>
                              Size: {res.file_size > 1024 ? `${(res.file_size / 1024).toFixed(1)} KB` : `${res.file_size} B`}
                            </span>
                          )}
                          {res.severity && <span>Severity: <strong className="uppercase" style={{ color: badgeColor }}>{res.severity}</strong></span>}
                          {res.incident_id && <span>Incident: {res.incident_id}</span>}
                        </div>

                        {res.findings && res.findings.length > 0 ? (
                          <div className="mt-2 space-y-1">
                            <p className="text-[10px] text-slate-400 uppercase font-semibold">Sensitive Data Discovered:</p>
                            <div className="flex flex-wrap gap-1.5">
                              {res.findings.map((f: any, fIdx: number) => (
                                <span
                                  key={fIdx}
                                  className="text-[11px] px-2 py-0.5 rounded font-mono"
                                  style={{ background: "rgba(255,59,59,0.1)", color: "#fca5a5", border: "1px solid rgba(255,59,59,0.2)" }}
                                >
                                  {f.rule}: {f.matched_text}
                                </span>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <p className="text-[11px] text-slate-400">Clean file — no sensitive PII or credentials detected.</p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="pt-4 border-t border-slate-800 flex items-center justify-between">
              <a
                href="/incidents"
                className="text-xs text-cyan-400 hover:text-cyan-300 font-semibold flex items-center gap-1"
              >
                <span>View All Recorded Incidents</span>
                <span>↗</span>
              </a>
              <button
                type="button"
                onClick={() => setScanResultData(null)}
                className="px-5 py-2 rounded-lg text-xs font-semibold text-white bg-slate-800 hover:bg-slate-700"
              >
                Close Summary
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
