"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";

// ─── Types ────────────────────────────────────────────────────────────────────
type Phase =
  | "connecting"
  | "enrolling"
  | "enrolled"
  | "scanning"
  | "done"
  | "error"
  | "expired";

interface SseEvent {
  type: string;
  [key: string]: unknown;
}

interface FindingAlert {
  filename: string;
  severity: string;
  category: string;
  description: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function getApiBase(): string {
  if (typeof window === "undefined") return "";
  const env = process.env.NEXT_PUBLIC_API_URL?.trim();
  const currentHost = window.location.hostname;
  const isDeployedHost = currentHost.endsWith(".vercel.app") || currentHost.endsWith(".render.com") || (!currentHost.includes("localhost") && !currentHost.includes("127.0.0.1"));
  
  // If deployed or env contains old devtunnels URL, use official deployed Render backend
  if (env && !env.includes("devtunnels.ms")) {
    return env.replace(/\/+$/, "");
  }
  return "https://dataghost.onrender.com";
}

function severityColor(sev: string) {
  if (sev === "CRITICAL") return "#ff3b3b";
  if (sev === "HIGH")     return "#ff9f0a";
  if (sev === "MEDIUM")   return "#f59e0b";
  return "#34d058";
}

// ─── Step Bar ─────────────────────────────────────────────────────────────────
const STEPS = ["Connect", "Enroll", "Scan", "Done"] as const;
const PHASE_STEP: Record<Phase, number> = {
  connecting: 0, enrolling: 1, enrolled: 1, scanning: 2, done: 3, error: 1, expired: 0,
};

function StepBar({ phase }: { phase: Phase }) {
  const active = PHASE_STEP[phase];
  return (
    <div className="flex items-start gap-0 mb-7">
      {STEPS.map((label, i) => (
        <div key={label} className="flex items-center flex-1">
          <div className="flex flex-col items-center flex-shrink-0" style={{ minWidth: 36 }}>
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-500"
              style={{
                background:
                  i < active
                    ? "linear-gradient(135deg,#00d4ff,#0089b2)"
                    : i === active
                    ? "linear-gradient(135deg,#34d058,#00a83e)"
                    : "rgba(30,58,95,0.4)",
                color: i <= active ? "#fff" : "#334155",
                boxShadow: i === active ? "0 0 14px rgba(52,208,88,0.5)" : "none",
              }}
            >
              {i < active ? "✓" : i + 1}
            </div>
            <span className="text-[10px] mt-1" style={{ color: i <= active ? "#64748b" : "#1e3a5f" }}>
              {label}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <div
              className="flex-1 h-px mx-1 mt-[-10px] transition-all duration-700"
              style={{
                background: i < active
                  ? "linear-gradient(90deg,#00d4ff,#34d058)"
                  : "#1a2744",
              }}
            />
          )}
        </div>
      ))}
    </div>
  );
}

// ─── Spinner ──────────────────────────────────────────────────────────────────
function Spinner({ color = "#00d4ff", size = 36 }: { color?: string; size?: number }) {
  return (
    <div
      className="rounded-full border-2 animate-spin"
      style={{
        width: size,
        height: size,
        borderColor: `${color}30`,
        borderTopColor: color,
      }}
    />
  );
}

// ─── File Scanner Row ─────────────────────────────────────────────────────────
function FileRow({ filename, index, total }: { filename: string; index: number; total: number }) {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  const icons: Record<string, string> = {
    csv: "📊", json: "📋", txt: "📄", py: "🐍", js: "⚡", ts: "⚡",
    sql: "🗃️", pdf: "📕", doc: "📝", docx: "📝", env: "🔑",
    key: "🔑", pem: "🔒", log: "📜", xml: "📐", yml: "⚙️", yaml: "⚙️",
  };
  const icon = icons[ext] ?? "📁";
  const pct = Math.round((index / total) * 100);

  return (
    <div className="flex items-center gap-2 text-xs animate-fade-up">
      <span style={{ fontSize: 14 }}>{icon}</span>
      <span className="font-mono truncate flex-1" style={{ color: "#94a3b8", maxWidth: 260 }}>
        {filename}
      </span>
      <span style={{ color: "#475569" }}>{pct}%</span>
    </div>
  );
}

// ─── Finding Badge ────────────────────────────────────────────────────────────
function FindingBadge({ f }: { f: FindingAlert }) {
  const c = severityColor(f.severity);
  return (
    <div
      className="rounded-lg px-3 py-2 text-xs animate-fade-up"
      style={{ background: `${c}0d`, border: `1px solid ${c}30` }}
    >
      <div className="flex items-center gap-2">
        <span className="font-bold" style={{ color: c }}>⚠ {f.severity}</span>
        <span style={{ color: "#64748b" }}>{f.filename}</span>
      </div>
      <p className="mt-0.5" style={{ color: "#94a3b8" }}>{f.category} — {f.description}</p>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function EnrollPage() {
  const params = useParams();
  const rawCode = Array.isArray(params?.code) ? params.code[0] : (params?.code ?? "");
  const code = rawCode.trim().toUpperCase();

  const [phase, setPhase] = useState<Phase>("connecting");
  const [deviceId, setDeviceId] = useState("");
  const [deviceName, setDeviceName] = useState("");
  const [platform, setPlatform] = useState("");
  const [currentFile, setCurrentFile] = useState("");
  const [fileIndex, setFileIndex] = useState(0);
  const [totalFiles, setTotalFiles] = useState(0);
  const [findings, setFindings] = useState<FindingAlert[]>([]);
  const [finalStats, setFinalStats] = useState<{ files: number; findings: number; incidents: number } | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [logLines, setLogLines] = useState<string[]>([]);
  const [isManualScanning, setIsManualScanning] = useState(false);
  const [scannedFilesCount, setScannedFilesCount] = useState(0);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const evtRef = useRef<EventSource | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  const handleManualScanFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setIsManualScanning(true);
    setPhase("scanning");
    setTotalFiles(files.length);
    setFileIndex(0);
    const ts = new Date().toLocaleTimeString();
    addLog(`[${ts}] 📂 Reading ${files.length} real files from your device…`);

    const apiBase = getApiBase();
    let currentFindings = 0;
    let currentIncidents = 0;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      setCurrentFile(file.name);
      setFileIndex(i + 1);

      try {
        const text = await file.text();
        const res = await fetch(`${apiBase}/api/scan/file`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            filename: file.name,
            content: text,
            device_id: deviceId || "android-device",
            destination: "INTERNAL",
            action: "SCAN",
          }),
        });

        if (res.ok) {
          const result = await res.json();
          if (Array.isArray(result.findings) && result.findings.length > 0) {
            for (const f of result.findings) {
              currentFindings++;
              const alert: FindingAlert = {
                filename: file.name,
                severity: f.severity || "MEDIUM",
                category: f.category || "SENSITIVE_DATA",
                description: f.detail || f.rule || "Sensitive pattern detected",
              };
              setFindings((prev) => [alert, ...prev].slice(0, 50));
              addLog(`[${new Date().toLocaleTimeString()}] ⚠ ${alert.severity}: ${file.name} (${alert.category})`);
            }
          }
          if (result.incident_id || (result.risk_score && result.risk_score >= 30)) {
            currentIncidents++;
          }
        }
      } catch (scanErr) {
        // ignore read failures on binary or protected files
      }
    }

    setFinalStats({
      files: files.length,
      findings: currentFindings,
      incidents: currentIncidents,
    });
    setPhase("done");
    setIsManualScanning(false);
    addLog(`[${new Date().toLocaleTimeString()}] ✅ Real device file scan completed!`);
  };

  const addLog = (msg: string) =>
    setLogLines((prev) => [...prev.slice(-60), msg]);

  // ── Auto-start SSE stream on mount with intelligent retry ──────────────────
  const [retryCount, setRetryCount] = useState(0);

  const startStream = () => {
    if (!code) {
      setErrorMsg("No enrollment code in URL.");
      setPhase("error");
      return;
    }

    if (evtRef.current) {
      evtRef.current.close();
      evtRef.current = null;
    }

    const apiBase = getApiBase();
    // Detect platform and device name from navigator
    let detectedPlatform = "Windows";
    let detectedDeviceName = "";
    if (typeof navigator !== "undefined") {
      const ua = navigator.userAgent.toLowerCase();
      if (ua.includes("android")) {
        detectedPlatform = "Android";
        const match = navigator.userAgent.match(/;\s*([^;]+?)\s*Build\//i);
        detectedDeviceName = match ? `Android-${match[1].trim()}` : "Android-Phone";
      } else if (ua.includes("iphone")) {
        detectedPlatform = "iOS";
        detectedDeviceName = "Apple-iPhone";
      } else if (ua.includes("ipad")) {
        detectedPlatform = "iOS";
        detectedDeviceName = "Apple-iPad";
      } else if (ua.includes("macintosh") || ua.includes("mac os x")) {
        detectedPlatform = "macOS";
        detectedDeviceName = "MacBook";
      } else if (ua.includes("linux")) {
        detectedPlatform = "Linux";
        detectedDeviceName = "Linux-Endpoint";
      } else {
        detectedPlatform = "Windows";
        detectedDeviceName = "Windows-PC";
      }
    }

    const url = `${apiBase}/api/devices/auto-enroll-scan?code=${encodeURIComponent(code)}&platform=${encodeURIComponent(detectedPlatform)}${detectedDeviceName ? `&device_name=${encodeURIComponent(detectedDeviceName)}` : ""}`;
    addLog(`[${new Date().toLocaleTimeString()}] Connecting as ${detectedPlatform} device…`);

    let retryTimer: NodeJS.Timeout | null = null;
    let attempts = 0;
    const maxAttempts = 6;

    const connect = () => {
      attempts++;
      const es = new EventSource(url);
      evtRef.current = es;

      es.onmessage = (ev) => {
        let data: SseEvent;
        try { data = JSON.parse(ev.data); } catch { return; }

        const ts = new Date().toLocaleTimeString();

        switch (data.type) {
          case "connected":
            addLog(`[${ts}] ✓ Connected to server`);
            setPhase("enrolling");
            break;

          case "enrolling":
            addLog(`[${ts}] ⟳ Validating code ${data.enrollment_code}…`);
            setPhase("enrolling");
            break;

          case "enrolled":
          case "already_enrolled": {
            const did = String(data.device_id ?? "");
            const dn  = String(data.device_name ?? "");
            const plt = String(data.platform ?? "");
            setDeviceId(did);
            setDeviceName(dn);
            setPlatform(plt);
            addLog(`[${ts}] ✓ Enrolled — ${dn} (${did})`);
            setPhase("enrolled");
            break;
          }

          case "waiting_for_agent": {
            addLog(`[${ts}] ⏳ Waiting for DataGhost Agent to connect`);
            break;
          }

          case "scan_start": {
            const tot = Number(data.total_files ?? 0);
            setTotalFiles(tot);
            addLog(`[${ts}] 🔍 Scan started — File 1 to File ${tot}`);
            setPhase("scanning");
            break;
          }

          case "scanning_file": {
            const fn  = String(data.filename ?? "");
            const idx = Number(data.index ?? 0);
            const tot = Number(data.total ?? 0);
            setCurrentFile(fn);
            setFileIndex(idx);
            setTotalFiles(tot);
            if (idx % 10 === 0 || idx === 1 || idx === tot)
              addLog(`[${ts}] [${idx}/${tot}] ${fn}`);
            break;
          }

          case "finding": {
            const f: FindingAlert = {
              filename: String(data.filename ?? ""),
              severity: String(data.severity ?? "LOW"),
              category: String(data.category ?? ""),
              description: String(data.description ?? ""),
            };
            setFindings((prev) => [f, ...prev].slice(0, 50));
            addLog(`[${ts}] ⚠ ${f.severity}: ${f.filename} — ${f.category}`);
            break;
          }

          case "scan_complete": {
            const stats = {
              files:     Number(data.files_scanned ?? 0),
              findings:  Number(data.findings ?? 0),
              incidents: Number(data.incidents ?? 0),
            };
            setFinalStats(stats);
            addLog(`[${ts}] ✅ Done — ${stats.files} files, ${stats.findings} findings, ${stats.incidents} incidents`);
            setPhase("done");
            es.close();
            break;
          }

          case "error":
            setErrorMsg(String(data.message ?? "Unknown error"));
            setPhase("error");
            addLog(`[${ts}] ✗ Error: ${data.message}`);
            es.close();
            break;

          case "expired":
            setPhase("expired");
            es.close();
            break;
        }
      };

      es.onerror = () => {
        es.close();
        if (attempts < maxAttempts) {
          addLog(`[${new Date().toLocaleTimeString()}] Server waking up... auto-retrying (${attempts}/${maxAttempts})`);
          retryTimer = setTimeout(connect, 4000);
        } else {
          setErrorMsg("Connection lost. The backend server may still be waking up. Click 'Retry' below.");
          setPhase("error");
          addLog(`[${new Date().toLocaleTimeString()}] ✗ Connection failed after ${maxAttempts} attempts`);
        }
      };
    };

    connect();

    return () => {
      if (retryTimer) clearTimeout(retryTimer);
      if (evtRef.current) {
        evtRef.current.close();
        evtRef.current = null;
      }
    };
  };

  useEffect(() => {
    const cleanup = startStream();
    return () => {
      cleanup?.();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, retryCount]);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logLines]);

  const pct = totalFiles > 0 ? Math.round((fileIndex / totalFiles) * 100) : 0;
  const dashboardUrl = "https://dataghost-five.vercel.app/devices";

  // ─── Render ───────────────────────────────────────────────────────────────
  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center p-4"
      style={{ background: "linear-gradient(135deg,#040a17 0%,#0a0f1e 50%,#060d1f 100%)" }}
    >
      {/* Ambient glow */}
      <div
        className="fixed top-0 left-1/2 -translate-x-1/2 w-[700px] h-96 pointer-events-none"
        style={{
          background: "radial-gradient(circle,rgba(0,212,255,0.06) 0%,transparent 70%)",
          filter: "blur(60px)",
        }}
      />

      <div
        className="w-full max-w-lg rounded-2xl shadow-2xl p-7 relative"
        style={{ background: "rgba(9,15,29,0.98)", border: "1px solid #1a2744", backdropFilter: "blur(20px)" }}
      >
        {/* Top gradient bar */}
        <div
          className="absolute top-0 left-0 right-0 h-0.5 rounded-t-2xl"
          style={{ background: "linear-gradient(90deg,transparent,#00d4ff,#34d058,transparent)" }}
        />

        {/* Header */}
        <div className="flex items-center gap-3 mb-5">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center font-black text-sm flex-shrink-0"
            style={{ background: "linear-gradient(135deg,#0089b2,#00d4ff)", color: "#fff" }}
          >
            DG
          </div>
          <div>
            <h1 className="text-white font-bold text-base leading-tight">DataGhost</h1>
            <p className="text-xs" style={{ color: "#475569" }}>
              Zero-Touch Enrollment &amp; DLP Scan
            </p>
          </div>
          {code && (
            <span
              className="ml-auto font-mono text-xs px-2 py-1 rounded"
              style={{
                background: "rgba(0,212,255,0.08)",
                border: "1px solid rgba(0,212,255,0.2)",
                color: "#00d4ff",
              }}
            >
              {code}
            </span>
          )}
        </div>

        <StepBar phase={phase} />

        {/* ── CONNECTING / ENROLLING ── */}
        {(phase === "connecting" || phase === "enrolling" || phase === "enrolled") && (
          <div className="text-center py-6 space-y-4">
            <Spinner size={40} />
            <p className="font-semibold" style={{ color: "#e2e8f0" }}>
              {phase === "connecting" && "Connecting to DataGhost server…"}
              {phase === "enrolling"  && `Validating enrollment code ${code}…`}
              {phase === "enrolled"   && `Device registered — starting scan…`}
            </p>
            {deviceName && (
              <p className="text-xs" style={{ color: "#64748b" }}>
                {deviceName} · {deviceId}
              </p>
            )}
          </div>
        )}

        {/* ── SCANNING ── */}
        {phase === "scanning" && (
          <div className="space-y-4">
            {/* Device info */}
            {deviceName && (
              <div
                className="flex items-center gap-3 px-3 py-2 rounded-lg"
                style={{ background: "rgba(0,212,255,0.05)", border: "1px solid rgba(0,212,255,0.12)" }}
              >
                <span style={{ fontSize: 18 }}>
                  {platform.toLowerCase().includes("win") ? "🪟" :
                   platform.toLowerCase().includes("android") ? "🤖" :
                   platform.toLowerCase().includes("mac") ? "🍎" :
                   platform.toLowerCase().includes("linux") ? "🐧" : "🖥️"}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold truncate" style={{ color: "#e2e8f0" }}>{deviceName}</p>
                  <p className="text-[10px]" style={{ color: "#475569" }}>{deviceId}</p>
                </div>
                <span
                  className="text-[10px] font-bold px-2 py-0.5 rounded"
                  style={{ background: "rgba(52,208,88,0.1)", color: "#34d058", border: "1px solid #34d05830" }}
                >
                  ENROLLED
                </span>
              </div>
            )}

            {/* Progress bar with Starting & Ending Points */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-[11px]" style={{ color: "#475569" }}>
                <span>Scanning files for sensitive data…</span>
                <span style={{ color: "#00d4ff", fontWeight: 700 }}>
                  {fileIndex}/{totalFiles} ({pct}%)
                </span>
              </div>
              <div className="h-2.5 rounded-full overflow-hidden" style={{ background: "#0a1628", border: "1px solid rgba(255,255,255,0.05)" }}>
                <div
                  className="h-full rounded-full transition-all duration-300"
                  style={{
                    width: `${Math.max(5, Math.min(100, pct))}%`,
                    background: "linear-gradient(90deg,#00d4ff,#34d058)",
                    boxShadow: "0 0 8px rgba(0,212,255,0.4)",
                  }}
                />
              </div>
              <div className="flex justify-between items-center text-[10px] text-slate-400 font-mono px-0.5">
                <span>🟢 Start: File 1</span>
                <span className="text-cyan-400 font-semibold">{pct}%</span>
                <span>🏁 End: File {totalFiles}</span>
              </div>
            </div>

            {/* Current file */}
            {currentFile && (
              <FileRow filename={currentFile} index={fileIndex} total={totalFiles} />
            )}

            {/* Live findings */}
            {findings.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-[10px] uppercase tracking-wider" style={{ color: "#475569" }}>
                  Live Findings ({findings.length})
                </p>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {findings.slice(0, 5).map((f, i) => (
                    <FindingBadge key={i} f={f} />
                  ))}
                </div>
              </div>
            )}

            {/* Activity log */}
            <div
              ref={logRef}
              className="rounded-lg p-2.5 font-mono text-[10px] max-h-28 overflow-y-auto"
              style={{ background: "#040a17", border: "1px solid #1a2744", color: "#1e4d7f" }}
            >
              {logLines.map((l, i) => (
                <div key={i} style={{ color: l.includes("⚠") ? "#ff9f0a" : l.includes("✓") || l.includes("✅") ? "#34d058" : "#1e4d7f" }}>
                  {l}
                </div>
              ))}
              <div style={{ color: "#00d4ff" }}>▋</div>
            </div>
          </div>
        )}

        {/* ── DONE ── */}
        {phase === "done" && finalStats && (
          <div className="space-y-5">
            <div className="text-center">
              <div className="text-5xl mb-3">✅</div>
              <p className="text-xl font-bold" style={{ color: "#34d058" }}>
                Full-Disk Scan Complete!
              </p>
              <p className="text-sm mt-1" style={{ color: "#94a3b8" }}>
                {deviceName} is now actively protected by DataGhost DLP.
              </p>
            </div>

            {/* Stats */}
            <div
              className="grid grid-cols-3 gap-3 text-center rounded-xl p-4"
              style={{ background: "rgba(52,208,88,0.04)", border: "1px solid rgba(52,208,88,0.15)" }}
            >
              {[
                { label: "Files Scanned", value: finalStats.files, color: "#00d4ff" },
                { label: "Findings", value: finalStats.findings, color: "#ff9f0a" },
                { label: "Incidents", value: finalStats.incidents, color: "#ff3b3b" },
              ].map((s) => (
                <div key={s.label}>
                  <p className="text-2xl font-bold" style={{ color: s.color }}>{s.value}</p>
                  <p className="text-[10px] mt-0.5" style={{ color: "#475569" }}>{s.label}</p>
                </div>
              ))}
            </div>

            {/* Device info */}
            <div className="text-xs space-y-1.5" style={{ color: "#475569" }}>
              {[
                ["Device", deviceName],
                ["ID", deviceId],
                ["Platform", platform],
                ["Code", code],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span>{k}</span>
                  <span className="font-mono" style={{ color: "#94a3b8" }}>{v}</span>
                </div>
              ))}
            </div>

            {/* Findings list */}
            {findings.length > 0 && (
              <div className="space-y-1.5">
                <p className="text-[10px] uppercase tracking-wider" style={{ color: "#475569" }}>
                  Detected Findings
                </p>
                <div className="space-y-1 max-h-36 overflow-y-auto">
                  {findings.map((f, i) => <FindingBadge key={i} f={f} />)}
                </div>
              </div>
            )}

            {/* Scan Real Device Files Button */}
            <div className="pt-2">
              <input
                type="file"
                multiple
                ref={fileInputRef}
                onChange={handleManualScanFiles}
                className="hidden"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isManualScanning}
                className="w-full py-2.5 rounded-xl font-bold text-xs flex items-center justify-center gap-2 transition-all mb-2 cursor-pointer hover:brightness-110 active:scale-98"
                style={{
                  background: "rgba(0,212,255,0.12)",
                  border: "1px solid rgba(0,212,255,0.4)",
                  color: "#00d4ff",
                  boxShadow: "0 0 12px rgba(0,212,255,0.15)",
                }}
              >
                <span>📁</span>
                <span>{isManualScanning ? "Scanning Device Files…" : "Scan Real Files from this Device (Upload / Pick)"}</span>
              </button>
            </div>

            <a
              href={dashboardUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="w-full py-3 rounded-xl font-bold text-sm text-center flex items-center justify-center gap-2 transition-all"
              style={{
                background: "linear-gradient(135deg,#0a3320,#0d4f2c)",
                border: "1px solid rgba(52,208,88,0.3)",
                color: "#34d058",
                boxShadow: "0 4px 20px rgba(52,208,88,0.15)",
              }}
            >
              📊 View Results in Dashboard →
            </a>
          </div>
        )}

        {/* ── EXPIRED ── */}
        {phase === "expired" && (
          <div className="text-center space-y-4 py-6">
            <div className="text-4xl">⏰</div>
            <p className="font-bold" style={{ color: "#ff9f0a" }}>Enrollment Code Expired</p>
            <p className="text-sm" style={{ color: "#64748b" }}>
              Code <strong style={{ color: "#94a3b8" }}>{code}</strong> has expired.
              Ask your admin to generate a new one.
            </p>
            <a
              href={dashboardUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block px-5 py-2 rounded-lg text-sm font-semibold"
              style={{
                background: "rgba(255,159,10,0.1)",
                border: "1px solid rgba(255,159,10,0.3)",
                color: "#ff9f0a",
              }}
            >
              Go to Dashboard
            </a>
          </div>
        )}

        {/* ── ERROR ── */}
        {phase === "error" && (
          <div className="space-y-4">
            <div
              className="rounded-xl px-4 py-3 text-sm"
              style={{
                background: "rgba(255,59,59,0.06)",
                border: "1px solid rgba(255,59,59,0.2)",
                color: "#ff3b3b",
              }}
            >
              <p className="font-bold mb-1">⚠ Connection Error</p>
              <p style={{ color: "#ff6b6b" }}>{errorMsg}</p>
            </div>

            {/* Still show log */}
            {logLines.length > 0 && (
              <div
                ref={logRef}
                className="rounded-lg p-2.5 font-mono text-[10px] max-h-28 overflow-y-auto"
                style={{ background: "#040a17", border: "1px solid #1a2744", color: "#1e4d7f" }}
              >
                {logLines.map((l, i) => <div key={i}>{l}</div>)}
              </div>
            )}

            <button
              onClick={() => {
                setRetryCount((c) => c + 1);
              }}
              className="w-full py-2.5 rounded-xl text-sm font-semibold transition-all hover:brightness-110 active:scale-98"
              style={{
                background: "rgba(255,59,59,0.15)",
                border: "1px solid rgba(255,59,59,0.3)",
                color: "#ff3b3b",
                cursor: "pointer",
              }}
            >
              Retry
            </button>
          </div>
        )}

        {/* Footer */}
        <p className="text-center text-[10px] mt-6" style={{ color: "#1e3a5f" }}>
          DataGhost DLP · Zero-Touch Enrollment · End-to-End Scan
        </p>
      </div>
    </div>
  );
}
