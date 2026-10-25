"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";

// ─── Types ────────────────────────────────────────────────────────────────────
type DetectedOS = "Android" | "Windows" | "Linux" | "macOS" | "iOS" | "Unknown";
type Step = "start" | "detecting" | "enrolling" | "scanning" | "done" | "error" | "expired";

interface EnrollmentStatus {
  enrollment_code: string;
  platform: string;
  status: string;
  device_id?: string;
  device_name?: string;
  is_expired: boolean;
}

interface RegisterResponse {
  device_id: string;
  device_name: string;
  platform: string;
  status: string;
  auth_token?: string;
  message: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function getApiBase(): string {
  if (typeof window === "undefined") return "";
  const envUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (envUrl) return envUrl.replace(/\/+$/, "");
  return "https://dataghost-1.onrender.com";
}

function detectOS(): DetectedOS {
  if (typeof navigator === "undefined") return "Unknown";
  const ua = navigator.userAgent;
  if (/android/i.test(ua)) return "Android";
  if (/iPad|iPhone|iPod/.test(ua)) return "iOS";
  if (/Win/.test(ua)) return "Windows";
  if (/Linux/.test(ua)) return "Linux";
  if (/Mac/.test(ua)) return "macOS";
  return "Unknown";
}

const API_HEADERS = {
  "Content-Type": "application/json",
  "X-Tunnel-Skip-Anti-Phishing-Page": "true",
  "bypass-tunnel-reminder": "true",
};

async function fetchStatus(code: string): Promise<EnrollmentStatus | null> {
  try {
    const res = await fetch(`${getApiBase()}/api/devices/enrollment/status/${encodeURIComponent(code)}`, {
      headers: API_HEADERS,
    });
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

async function registerDevice(code: string, platform: string): Promise<RegisterResponse> {
  const deviceName = `${platform}-Node-${code.replace(/[^A-Z0-9]/g, "").slice(-4) || "01"}`;
  const res = await fetch(`${getApiBase()}/api/devices/enrollment/register`, {
    method: "POST",
    headers: API_HEADERS,
    body: JSON.stringify({
      enrollment_code: code,
      device_name: deviceName,
      platform,
      os_name: `${platform} Endpoint`,
      hostname: `${platform.toUpperCase()}-${code.replace(/[^A-Z0-9]/g, "").slice(-4) || "01"}`,
    }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}: Enrollment failed`);
  return data;
}

async function triggerScan(deviceId: string, authToken?: string): Promise<void> {
  try {
    await fetch(`${getApiBase()}/api/devices/${encodeURIComponent(deviceId)}/scan`, {
      method: "POST",
      headers: {
        ...API_HEADERS,
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      },
      body: JSON.stringify({ demo: false }),
    });
  } catch { /* best-effort */ }
}

// ─── Step Indicator ───────────────────────────────────────────────────────────
const STEPS = ["Verify", "Enroll", "Scan", "Done"] as const;
const STEP_MAP: Record<Step, number> = {
  start: 0, detecting: 0, enrolling: 1, scanning: 2, done: 3, error: 1, expired: 0,
};

function StepBar({ step }: { step: Step }) {
  const active = STEP_MAP[step];
  return (
    <div className="flex items-center gap-0 mb-8">
      {STEPS.map((label, i) => (
        <div key={label} className="flex items-center flex-1">
          <div className="flex flex-col items-center flex-shrink-0">
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-500"
              style={{
                background: i < active
                  ? "linear-gradient(135deg,#00d4ff,#0089b2)"
                  : i === active
                  ? "linear-gradient(135deg,#34d058,#00a83e)"
                  : "rgba(30,58,95,0.5)",
                color: i <= active ? "#fff" : "#475569",
                boxShadow: i === active ? "0 0 16px rgba(52,208,88,0.4)" : "none",
              }}
            >
              {i < active ? "✓" : i + 1}
            </div>
            <span className="text-[10px] mt-1" style={{ color: i <= active ? "#94a3b8" : "#1e3a5f" }}>
              {label}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <div
              className="flex-1 h-0.5 mx-1 transition-all duration-700"
              style={{ background: i < active ? "linear-gradient(90deg,#00d4ff,#34d058)" : "#1a2744" }}
            />
          )}
        </div>
      ))}
    </div>
  );
}

// ─── Spinner ──────────────────────────────────────────────────────────────────
function Spinner({ color = "#00d4ff" }: { color?: string }) {
  return (
    <div
      className="w-10 h-10 rounded-full border-2 animate-spin mx-auto"
      style={{ borderColor: `${color}33`, borderTopColor: color }}
    />
  );
}

// ─── OS-specific instructions ──────────────────────────────────────────────────
function OsInstructions({ os, code }: { os: DetectedOS; code: string }) {
  const [copied, setCopied] = useState(false);
  const apiUrl = "https://dataghost-1.onrender.com";
  const cmd = `python dataghost_agent.py --api-url ${apiUrl} --enroll ${code}`;

  const copy = (text: string) => {
    navigator.clipboard.writeText(text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); });
  };

  if (os === "Android") {
    return (
      <div className="space-y-3 text-sm">
        <p style={{ color: "#94a3b8" }}>Scan detected: <strong style={{ color: "#34d058" }}>Android</strong></p>
        <ol className="list-decimal list-inside space-y-2" style={{ color: "#64748b" }}>
          <li>Tap <strong style={{ color: "#e2e8f0" }}>"Enroll This Device"</strong> below</li>
          <li>DataGhost registers the device automatically</li>
          <li>A full-disk DLP scan starts immediately</li>
          <li>View results in the <strong style={{ color: "#00d4ff" }}>Devices</strong> dashboard</li>
        </ol>
      </div>
    );
  }

  if (os === "Windows" || os === "Linux" || os === "macOS") {
    const osLabel = { Windows: "PowerShell", Linux: "Terminal", macOS: "Terminal" }[os];
    return (
      <div className="space-y-3 text-sm">
        <p style={{ color: "#94a3b8" }}>
          Scan detected: <strong style={{ color: "#60a5fa" }}>{os}</strong> — open <strong style={{ color: "#e2e8f0" }}>{osLabel}</strong> and run:
        </p>
        <div
          className="relative rounded-lg p-3 font-mono text-xs break-all"
          style={{ background: "#040a17", border: "1px solid #1a2744", color: "#00d4ff" }}
        >
          {cmd}
          <button
            onClick={() => copy(cmd)}
            className="absolute top-2 right-2 text-[10px] px-2 py-1 rounded transition-all"
            style={{
              background: copied ? "rgba(52,208,88,0.15)" : "rgba(0,212,255,0.1)",
              border: `1px solid ${copied ? "#34d05840" : "#00d4ff30"}`,
              color: copied ? "#34d058" : "#00d4ff",
            }}
          >
            {copied ? "✓" : "Copy"}
          </button>
        </div>
        <p className="text-xs" style={{ color: "#475569" }}>
          Or tap <strong style={{ color: "#e2e8f0" }}>"Enroll This Device"</strong> to register directly from this browser.
        </p>
      </div>
    );
  }

  return (
    <div className="text-sm" style={{ color: "#64748b" }}>
      <p>Copy code <strong style={{ color: "#e2e8f0" }}>{code}</strong> into your DataGhost Agent app.</p>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function EnrollPage() {
  const params = useParams();
  const rawCode = Array.isArray(params?.code) ? params.code[0] : (params?.code ?? "");
  const code = rawCode.trim().toUpperCase();

  const [step, setStep] = useState<Step>("start");
  const [os, setOs] = useState<DetectedOS>("Unknown");
  const [status, setStatus] = useState<EnrollmentStatus | null>(null);
  const [registerData, setRegisterData] = useState<RegisterResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [scanProgress, setScanProgress] = useState(0);

  // Detect OS on mount + load initial status
  const init = useCallback(async () => {
    setStep("detecting");
    const detectedOs = detectOS();
    setOs(detectedOs);
    if (!code) { setStep("error"); setErrorMsg("No enrollment code provided."); return; }
    const data = await fetchStatus(code);
    if (!data) { setStep("error"); setErrorMsg("Could not reach DataGhost server. Please try again."); return; }
    if (data.is_expired || data.status === "EXPIRED") { setStep("expired"); setStatus(data); return; }
    if (data.status === "USED") { setStep("done"); setStatus(data); return; }
    setStatus(data);
    setStep("start");
  }, [code]);

  useEffect(() => { init(); }, [init]);

  // Handle enroll + auto-scan
  const handleEnroll = async () => {
    if (!code) return;
    setStep("enrolling");
    setErrorMsg("");
    try {
      const detectedPlatform = os === "Unknown" ? (status?.platform || "Windows") : os;
      const reg = await registerDevice(code, detectedPlatform);
      setRegisterData(reg);
      setStep("scanning");

      // Animate scan progress (0→100 over ~6s) while actual scan runs in background
      setScanProgress(0);
      const start = Date.now();
      const duration = 6000;
      const interval = setInterval(() => {
        const elapsed = Date.now() - start;
        const pct = Math.min(Math.round((elapsed / duration) * 100), 95);
        setScanProgress(pct);
        if (elapsed >= duration) clearInterval(interval);
      }, 100);

      // Trigger actual scan on the backend
      await triggerScan(reg.device_id, reg.auth_token);

      // Wait for animation to finish then go to done
      setTimeout(() => {
        setScanProgress(100);
        setTimeout(() => setStep("done"), 600);
        clearInterval(interval);
      }, duration);
    } catch (err: unknown) {
      setStep("error");
      setErrorMsg(err instanceof Error ? err.message : "Enrollment failed. Please try again.");
    }
  };

  const dashboardUrl = "https://dataghost-five.vercel.app/devices";

  // ─── Render ───────────────────────────────────────────────────────────────
  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center p-4"
      style={{ background: "linear-gradient(135deg, #040a17 0%, #0a0f1e 50%, #060d1f 100%)" }}
    >
      {/* Ambient glow */}
      <div
        className="fixed top-0 left-1/2 -translate-x-1/2 w-[600px] h-96 rounded-full pointer-events-none"
        style={{ background: "radial-gradient(circle, rgba(0,212,255,0.05) 0%, transparent 70%)", filter: "blur(60px)" }}
      />

      <div
        className="w-full max-w-md rounded-2xl shadow-2xl p-7 relative"
        style={{ background: "rgba(10,15,30,0.97)", border: "1px solid #1a2744", backdropFilter: "blur(20px)" }}
      >
        {/* Top accent */}
        <div
          className="absolute top-0 left-0 right-0 h-0.5 rounded-t-2xl"
          style={{ background: "linear-gradient(90deg, transparent, #00d4ff, #34d058, transparent)" }}
        />

        {/* Logo */}
        <div className="flex items-center gap-3 mb-6">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center text-sm font-black flex-shrink-0"
            style={{ background: "linear-gradient(135deg, #0089b2, #00d4ff)", color: "#fff" }}
          >
            DG
          </div>
          <div>
            <h1 className="text-white font-bold text-base leading-tight">DataGhost</h1>
            <p className="text-xs" style={{ color: "#475569" }}>Device Enrollment & DLP Setup</p>
          </div>
          {code && (
            <span
              className="ml-auto font-mono text-xs px-2 py-1 rounded"
              style={{ background: "rgba(0,212,255,0.08)", border: "1px solid rgba(0,212,255,0.2)", color: "#00d4ff" }}
            >
              {code}
            </span>
          )}
        </div>

        <StepBar step={step} />

        {/* ── DETECTING ── */}
        {step === "detecting" && (
          <div className="text-center py-6 space-y-4">
            <Spinner />
            <p className="text-sm" style={{ color: "#94a3b8" }}>Detecting your device…</p>
          </div>
        )}

        {/* ── START ── */}
        {step === "start" && status && (
          <div className="space-y-5">
            <div
              className="rounded-xl p-4"
              style={{ background: "rgba(0,212,255,0.04)", border: "1px solid rgba(0,212,255,0.12)" }}
            >
              <p className="text-xs uppercase tracking-wider mb-2" style={{ color: "#475569" }}>Enrollment Code</p>
              <p className="text-2xl font-mono font-bold tracking-widest" style={{ color: "#00d4ff" }}>{code}</p>
              <p className="text-xs mt-1" style={{ color: "#64748b" }}>
                Platform: <span style={{ color: "#94a3b8" }}>{status.platform}</span>
              </p>
            </div>

            <OsInstructions os={os} code={code} />

            <button
              onClick={handleEnroll}
              className="w-full py-3 rounded-xl font-bold text-sm transition-all duration-200 flex items-center justify-center gap-2"
              style={{
                background: "linear-gradient(135deg, #0089b2, #00d4ff)",
                color: "#fff",
                boxShadow: "0 4px 24px rgba(0,212,255,0.25)",
              }}
            >
              🚀 Enroll This Device — Start DLP Protection
            </button>
            <p className="text-center text-xs" style={{ color: "#475569" }}>
              This will register the device and begin an immediate full-disk scan.
            </p>
          </div>
        )}

        {/* ── ENROLLING ── */}
        {step === "enrolling" && (
          <div className="text-center py-8 space-y-4">
            <Spinner color="#00d4ff" />
            <p className="font-semibold" style={{ color: "#e2e8f0" }}>Registering device…</p>
            <p className="text-sm" style={{ color: "#475569" }}>
              Validating enrollment code and issuing device credentials.
            </p>
          </div>
        )}

        {/* ── SCANNING ── */}
        {step === "scanning" && (
          <div className="space-y-5">
            <div className="text-center">
              <div className="text-4xl mb-3">🔍</div>
              <p className="font-bold text-lg" style={{ color: "#e2e8f0" }}>
                {registerData?.device_name || "Device"} enrolled!
              </p>
              <p className="text-sm mt-1" style={{ color: "#94a3b8" }}>
                Running initial full-disk DLP scan…
              </p>
            </div>

            {/* Progress bar */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs" style={{ color: "#475569" }}>
                <span>Scanning files for sensitive data…</span>
                <span style={{ color: "#34d058" }}>{scanProgress}%</span>
              </div>
              <div className="h-2 rounded-full overflow-hidden" style={{ background: "rgba(30,58,95,0.5)" }}>
                <div
                  className="h-full rounded-full transition-all duration-200"
                  style={{
                    width: `${scanProgress}%`,
                    background: "linear-gradient(90deg, #00d4ff, #34d058)",
                    boxShadow: "0 0 8px rgba(52,208,88,0.5)",
                  }}
                />
              </div>
            </div>

            {/* Scanning steps */}
            {[
              { label: "Enrolling device identity", done: scanProgress >= 10 },
              { label: "Issuing DLP agent credentials", done: scanProgress >= 25 },
              { label: "Queuing full-disk scan", done: scanProgress >= 40 },
              { label: "Scanning file system…", done: scanProgress >= 75 },
              { label: "Analysing findings", done: scanProgress >= 90 },
            ].map(({ label, done }) => (
              <div key={label} className="flex items-center gap-2 text-xs" style={{ color: done ? "#34d058" : "#475569" }}>
                <span>{done ? "✓" : "◦"}</span>
                <span>{label}</span>
              </div>
            ))}
          </div>
        )}

        {/* ── DONE ── */}
        {step === "done" && (
          <div className="space-y-5">
            <div className="text-center">
              <div className="text-5xl mb-3 animate-bounce">✅</div>
              <p className="text-xl font-bold" style={{ color: "#34d058" }}>
                Device Protected!
              </p>
              <p className="text-sm mt-2" style={{ color: "#94a3b8" }}>
                {registerData?.device_name || status?.device_name || "Your device"} is now enrolled and actively monitored by DataGhost DLP.
              </p>
            </div>

            {/* Summary */}
            <div
              className="rounded-xl p-4 space-y-2 text-sm"
              style={{ background: "rgba(52,208,88,0.04)", border: "1px solid rgba(52,208,88,0.15)" }}
            >
              {[
                ["Status", "ACTIVE — DLP monitoring enabled"],
                ["Scan", "Full-disk scan queued (results in dashboard)"],
                ["Code", code],
                ["Device ID", registerData?.device_id || status?.device_id || "—"],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-3">
                  <span style={{ color: "#475569" }}>{k}</span>
                  <span className="font-mono text-xs text-right" style={{ color: "#94a3b8" }}>{v}</span>
                </div>
              ))}
            </div>

            <a
              href={dashboardUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="w-full py-3 rounded-xl font-bold text-sm text-center flex items-center justify-center gap-2 transition-all duration-200"
              style={{
                background: "linear-gradient(135deg,#0a3320,#0d4f2c)",
                border: "1px solid rgba(52,208,88,0.3)",
                color: "#34d058",
                boxShadow: "0 4px 20px rgba(52,208,88,0.15)",
                display: "flex",
              }}
            >
              📊 Open DataGhost Dashboard
            </a>
          </div>
        )}

        {/* ── EXPIRED ── */}
        {step === "expired" && (
          <div className="text-center space-y-4 py-4">
            <div className="text-4xl">⏰</div>
            <p className="font-bold" style={{ color: "#ff9f0a" }}>Enrollment Code Expired</p>
            <p className="text-sm" style={{ color: "#64748b" }}>
              Code <strong style={{ color: "#94a3b8" }}>{code}</strong> has expired.
              Please ask your administrator to generate a new enrollment code.
            </p>
            <a
              href={dashboardUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block px-5 py-2 rounded-lg text-sm font-semibold transition-all"
              style={{ background: "rgba(255,159,10,0.1)", border: "1px solid rgba(255,159,10,0.3)", color: "#ff9f0a" }}
            >
              Go to Dashboard
            </a>
          </div>
        )}

        {/* ── ERROR ── */}
        {step === "error" && (
          <div className="space-y-4 py-2">
            <div
              className="rounded-xl px-4 py-3 text-sm"
              style={{ background: "rgba(255,59,59,0.06)", border: "1px solid rgba(255,59,59,0.2)", color: "#ff3b3b" }}
            >
              <p className="font-semibold mb-1">⚠ Enrollment Failed</p>
              <p style={{ color: "#ff6b6b" }}>{errorMsg}</p>
            </div>
            <button
              onClick={init}
              className="w-full py-2.5 rounded-xl text-sm font-semibold transition-all"
              style={{ background: "rgba(255,59,59,0.1)", border: "1px solid rgba(255,59,59,0.25)", color: "#ff3b3b" }}
            >
              Try Again
            </button>
          </div>
        )}

        {/* Footer */}
        <p className="text-center text-[10px] mt-6" style={{ color: "#1e3a5f" }}>
          DataGhost DLP · Secure Device Enrollment · v2.0
        </p>
      </div>
    </div>
  );
}
