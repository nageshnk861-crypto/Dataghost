"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";

// ─── Platform Detection ────────────────────────────────────────────────────────
type DetectedOS = "Android" | "Windows" | "Linux" | "macOS" | "Unknown";

function detectOS(): DetectedOS {
  if (typeof navigator === "undefined") return "Unknown";
  const ua = navigator.userAgent;
  if (/android/i.test(ua)) return "Android";
  if (/iPad|iPhone|iPod/.test(ua)) return "Unknown"; // iOS not supported
  if (/Win/.test(ua)) return "Windows";
  if (/Linux/.test(ua)) return "Linux";
  if (/Mac/.test(ua)) return "macOS";
  return "Unknown";
}

// ─── Types ────────────────────────────────────────────────────────────────────
interface EnrollmentStatus {
  enrollment_code: string;
  platform: string;
  status: string;
  device_id?: string;
  device_name?: string;
  is_expired: boolean;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function getApiBase(): string {
  if (typeof window === "undefined") return "";
  const envUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (envUrl) return envUrl.replace(/\/+$/, "");
  return "";
}

async function fetchStatus(code: string): Promise<EnrollmentStatus | null> {
  try {
    const base = getApiBase();
    const url = `${base}/api/devices/enrollment/status/${encodeURIComponent(code)}`;
    console.log(`[fetchStatus] URL: ${url}`);
    const res = await fetch(url, {
      headers: {
        "X-Tunnel-Skip-Anti-Phishing-Page": "true",
        "bypass-tunnel-reminder": "true",
      },
    });
    console.log(`[fetchStatus] Response status: ${res.status}`);
    if (!res.ok) {
      const errorText = await res.text();
      console.log(`[fetchStatus] Error response: ${errorText}`);
      return null;
    }
    const data = await res.json();
    console.log(`[fetchStatus] Success:`, data);
    return data;
  } catch (err) {
    console.log(`[fetchStatus] Exception:`, err);
    return null;
  }
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function EnrollPage() {
  const params = useParams();
  const rawCode = Array.isArray(params?.code) ? params.code[0] : (params?.code ?? "");
  const code = rawCode.trim().toUpperCase();

  const [os, setOs] = useState<DetectedOS>("Unknown");
  const [status, setStatus] = useState<EnrollmentStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [enrolled, setEnrolled] = useState(false);
  const [enrolling, setEnrolling] = useState(false);
  const [enrollError, setEnrollError] = useState("");
  const [psCopied, setPsCopied] = useState(false);

  // Auto enroll this device directly via API
  const autoEnrollDevice = async () => {
    if (!code) return;
    setEnrolling(true);
    setEnrollError("");
    try {
      const base = getApiBase();
      const detectedPlatform = os === "Unknown" ? (status?.platform || "Windows") : os;
      const deviceName = `${detectedPlatform}-Node-${code.replace(/[^A-Z0-9]/g, "").slice(-4) || "01"}`;
      const res = await fetch(`${base}/api/devices/enrollment/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Tunnel-Skip-Anti-Phishing-Page": "true",
          "bypass-tunnel-reminder": "true",
        },
        body: JSON.stringify({
          enrollment_code: code,
          device_name: deviceName,
          platform: detectedPlatform,
          os_name: `${detectedPlatform} Endpoint`,
          hostname: `${detectedPlatform.toUpperCase()}-${code.replace(/[^A-Z0-9]/g, "").slice(-4) || "01"}`,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setStatus((prev) => ({
          ...(prev || { enrollment_code: code, platform: detectedPlatform, is_expired: false }),
          status: "USED",
          device_id: data.device_id,
          device_name: data.device_name || deviceName,
        }));
        setEnrolled(true);
      } else {
        const err = await res.json().catch(() => ({}));
        setEnrollError(err.detail || "Enrollment failed. Please try again.");
      }
    } catch (err: unknown) {
      setEnrollError(err instanceof Error ? err.message : "Failed to connect to backend server");
    } finally {
      setEnrolling(false);
    }
  };

  // Detect OS on mount
  useEffect(() => {
    setOs(detectOS());
  }, []);

  // Load enrollment info
  const loadStatus = useCallback(async () => {
    if (!code) {
      console.log("[loadStatus] No code provided");
      setLoading(false);
      return;
    }
    console.log(`[loadStatus] Loading status for code: ${code}`);
    const data = await fetchStatus(code);
    console.log(`[loadStatus] Received data:`, data);
    setStatus(data);
    if (data?.status === "USED") setEnrolled(true);
    setLoading(false);
  }, [code]);

  useEffect(() => {
    loadStatus();
    const iv = setInterval(() => {
      fetchStatus(code).then((d) => {
        if (d) setStatus(d);
        if (d?.status === "USED") { setEnrolled(true); clearInterval(iv); }
      });
    }, 3000);
    return () => clearInterval(iv);
  }, [code, loadStatus]);

  const copyCode = () => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const apkUrl = `${getApiBase()}/dataghost-agent.apk`;
  const isExpired = status?.is_expired || status?.status === "EXPIRED";

  // ─── OS-specific content ──────────────────────────────────────────────────────
  const osInfo: Record<DetectedOS, { icon: string; label: string; color: string; steps: string[]; downloadAvailable: boolean; downloadLabel?: string; downloadUrl?: string }> = {
    Android: {
      icon: "🤖",
      label: "Android detected",
      color: "#34d058",
      downloadAvailable: true,
      downloadLabel: "Download DataGhost Agent APK",
      downloadUrl: apkUrl,
      steps: [
        "Tap \"Download DataGhost Agent\" below",
        "Open the downloaded APK to install (allow unknown sources if prompted)",
        "Open DataGhost Agent → the enrollment code will be pre-filled",
        "Tap Enroll Device to complete registration",
      ],
    },
    Windows: {
      icon: "🪟",
      label: "Windows detected",
      color: "#60a5fa",
      downloadAvailable: false,
      steps: [
        "On your Windows machine, open PowerShell as Administrator",
        "Run the DataGhost Agent installer script from your IT team",
        "Enter the enrollment code below when prompted",
        "The agent will connect automatically after enrollment",
      ],
    },
    Linux: {
      icon: "🐧",
      label: "Linux detected",
      color: "#ff9f0a",
      downloadAvailable: false,
      steps: [
        "On your Linux machine, download the DataGhost Agent package",
        "Install using: sudo dpkg -i dataghost-agent.deb  (or .rpm)",
        "Run: dataghost-agent --enroll <ENROLLMENT_CODE>",
        "The agent will register and start monitoring",
      ],
    },
    macOS: {
      icon: "🍎",
      label: "macOS detected",
      color: "#a78bfa",
      downloadAvailable: false,
      steps: [
        "DataGhost macOS agent is not yet available",
        "Please contact your IT administrator for enrollment options",
      ],
    },
    Unknown: {
      icon: "💻",
      label: "Device detected",
      color: "#00d4ff",
      downloadAvailable: false,
      steps: [
        "Use the DataGhost Agent for your operating system",
        "Enter the enrollment code below during agent setup",
      ],
    },
  };

  const info = osInfo[os];

  // ─── Render ─────────────────────────────────────────────────────────────────
  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center p-4"
      style={{ background: "linear-gradient(135deg, #040a17 0%, #0a0f1e 50%, #060d1f 100%)" }}
    >
      {/* Ambient glow */}
      <div
        className="fixed top-0 left-1/2 -translate-x-1/2 w-96 h-96 rounded-full pointer-events-none"
        style={{
          background: "radial-gradient(circle, rgba(0,212,255,0.04) 0%, transparent 70%)",
          filter: "blur(40px)",
        }}
      />

      {/* Card */}
      <div
        className="w-full max-w-md rounded-2xl shadow-2xl p-7 relative overflow-hidden"
        style={{
          background: "rgba(10,15,30,0.95)",
          border: "1px solid #1a2744",
          backdropFilter: "blur(20px)",
        }}
      >
        {/* Top accent */}
        <div
          className="absolute top-0 left-0 right-0 h-0.5"
          style={{ background: "linear-gradient(90deg, transparent, #00d4ff, transparent)" }}
        />

        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center text-lg font-black"
            style={{ background: "linear-gradient(135deg, #0089b2, #00d4ff)", color: "#fff" }}
          >
            DG
          </div>
          <div>
            <p className="text-white font-bold text-sm">DataGhost</p>
            <p className="text-slate-400 text-xs">Device Enrollment</p>
          </div>
        </div>

        {loading ? (
          <div className="flex flex-col items-center gap-4 py-10">
            <div
              className="w-8 h-8 border-2 border-transparent border-t-cyan-400 rounded-full animate-spin"
            />
            <p className="text-slate-400 text-sm">Verifying enrollment code…</p>
          </div>
        ) : !code || !status ? (
          /* Invalid code */
          <div className="text-center py-8 space-y-3">
            <p className="text-4xl">❌</p>
            <p className="text-white font-bold">Enrollment code not found</p>
            <p className="text-slate-400 text-sm">
              This link may be invalid or already used. Ask your IT admin to generate a new enrollment code.
            </p>
          </div>
        ) : isExpired ? (
          /* Expired */
          <div
            className="rounded-xl p-5 text-center space-y-3"
            style={{ background: "rgba(255,59,59,0.06)", border: "1px solid rgba(255,59,59,0.2)" }}
          >
            <p className="text-4xl">⏱️</p>
            <p className="font-bold text-red-400">Enrollment Code Expired</p>
            <p className="text-slate-400 text-sm">
              Ask your IT administrator to generate a new enrollment code.
            </p>
          </div>
        ) : enrolled ? (
          /* Success */
          <div
            className="rounded-xl p-5 text-center space-y-3"
            style={{ background: "rgba(52,208,88,0.06)", border: "1px solid rgba(52,208,88,0.2)" }}
          >
            <p className="text-4xl">🎉</p>
            <p className="font-bold text-green-400">Enrollment Successful!</p>
            <p className="text-slate-400 text-sm">
              Device <strong className="text-white">{status?.device_name || "registered"}</strong> has
              joined DataGhost DLP management.
            </p>
          </div>
        ) : (
          /* Active enrollment */
          <div className="space-y-5">
            {/* OS Badge */}
            <div
              className="flex items-center gap-3 px-4 py-3 rounded-xl"
              style={{ background: `${info.color}0d`, border: `1px solid ${info.color}30` }}
            >
              <span className="text-2xl">{info.icon}</span>
              <div>
                <p className="text-xs font-bold" style={{ color: info.color }}>
                  {info.label}
                </p>
                <p className="text-slate-400 text-xs">
                  {os === "Android"
                    ? "Agent-managed Android — no factory reset required"
                    : os === "Unknown"
                    ? "Use the correct agent for your platform"
                    : `${os} endpoint agent`}
                </p>
              </div>
            </div>

            {/* 1-Click Auto Enroll Action */}
            <div className="space-y-2">
              <button
                type="button"
                onClick={autoEnrollDevice}
                disabled={enrolling}
                className="w-full py-3.5 px-4 rounded-xl font-bold text-sm text-white flex items-center justify-center gap-2 shadow-lg transition-all hover:brightness-110 active:scale-95 disabled:opacity-60"
                style={{
                  background: "linear-gradient(135deg, #0089b2 0%, #00d4ff 100%)",
                  boxShadow: "0 4px 20px rgba(0, 212, 255, 0.35)",
                  border: "1px solid rgba(0, 212, 255, 0.5)",
                }}
              >
                {enrolling ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                    <span>Enrolling Device Automatically…</span>
                  </>
                ) : (
                  <>
                    <span className="text-base">⚡</span>
                    <span>Auto-Enroll This Device (1-Click Instant)</span>
                  </>
                )}
              </button>
              {enrollError && (
                <p className="text-xs text-red-400 text-center font-medium">{enrollError}</p>
              )}
            </div>

            {/* Enrollment Code */}
            <div className="space-y-1.5">
              <p className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">
                Enrollment Code
              </p>
              <div
                className="flex items-center justify-between px-4 py-3 rounded-xl"
                style={{ background: "rgba(0,212,255,0.06)", border: "1px solid rgba(0,212,255,0.2)" }}
              >
                <span
                  className="font-mono text-xl font-bold tracking-widest"
                  style={{ color: "#00d4ff" }}
                >
                  {code}
                </span>
                <button
                  onClick={copyCode}
                  className="text-xs px-3 py-1.5 rounded-lg transition-all"
                  style={{
                    background: "rgba(0,212,255,0.1)",
                    color: copied ? "#34d058" : "#00d4ff",
                    border: "1px solid rgba(0,212,255,0.2)",
                  }}
                >
                  {copied ? "✓ Copied" : "Copy"}
                </button>
              </div>
            </div>

            {/* Steps */}
            <div className="space-y-2">
              <p className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">
                Setup Instructions
              </p>
              <ol className="space-y-2">
                {info.steps.map((step, i) => (
                  <li key={i} className="flex gap-3 items-start">
                    <span
                      className="flex-shrink-0 w-5 h-5 rounded-full text-[10px] font-bold flex items-center justify-center mt-0.5"
                      style={{ background: `${info.color}20`, color: info.color, border: `1px solid ${info.color}40` }}
                    >
                      {i + 1}
                    </span>
                    <p
                      className="text-sm text-slate-300 leading-snug"
                      dangerouslySetInnerHTML={{ __html: step.replace("<ENROLLMENT_CODE>", `<code class="text-cyan-400 font-mono">${code}</code>`) }}
                    />
                  </li>
                ))}
              </ol>
            </div>

            {/* Download Button — only for platforms where agent exists */}
            {info.downloadAvailable && info.downloadUrl && (
              <a
                href={info.downloadUrl}
                download="dataghost-agent.apk"
                className="flex items-center justify-center gap-2 w-full py-3.5 rounded-xl font-semibold text-white text-sm transition-all hover:brightness-110 active:scale-95 shadow-lg"
                style={{
                  background: "linear-gradient(135deg, #0089b2, #00d4ff)",
                  border: "1px solid rgba(0,212,255,0.4)",
                  textDecoration: "none",
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                  <path d="M12 15l-4-4h2.5V5h3v6H16l-4 4zM5 19h14v-2H5v2z" fill="currentColor" />
                </svg>
                {info.downloadLabel}
              </a>
            )}

            {/* Windows/Linux instruction note */}
            {!info.downloadAvailable && os !== "macOS" && os !== "Unknown" && (
              <div
                className="px-4 py-3 rounded-xl text-xs text-slate-400"
                style={{ background: "rgba(15,23,41,0.8)", border: "1px solid #1a2744" }}
              >
                💡 Contact your IT administrator for the {os} DataGhost Agent installer package.
              </div>
            )}

            {/* Live status dot */}
            <div className="flex items-center justify-center gap-2 pt-1">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
              <span className="text-[11px] text-slate-400">Waiting for device registration…</span>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <p className="text-slate-600 text-xs mt-5">
        DataGhost DLP Platform · Secure Enrollment Portal
      </p>
    </div>
  );
}
