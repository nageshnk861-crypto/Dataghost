"use client";

import { useRef, useState, useCallback, useId } from "react";
import Sidebar, { toggleSidebar } from "../../components/Sidebar";
import ScanResult from "../../components/ScanResult";
import type { ScanResultData } from "../../components/ScanResult";
import { scanFile, scanText } from "@/lib/api";
import { useAuthGuard } from "@/lib/useAuthGuard";

// ─── Constants ────────────────────────────────────────────────────────────────
const MAX_FILE_SIZE_MB = 50;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;
const ALLOWED_EXTENSIONS = [
  ".txt", ".csv", ".json", ".pdf", ".docx", ".xlsx",
  ".log", ".env", ".py", ".js", ".ts", ".yaml", ".yml",
  ".sql", ".sh", ".bash", ".conf", ".cfg", ".ini", ".toml",
  ".zip", ".tar", ".gz",
];

// ─── Types ───────────────────────────────────────────────────────────────────
type FileStatus = "queued" | "scanning" | "done" | "error";

interface QueuedFile {
  id: string;
  file: File;
  status: FileStatus;
  result?: ScanResultData;
  error?: string;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getExt(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot).toLowerCase() : "";
}

function validateFile(file: File): string | null {
  if (file.size === 0) return "File is empty.";
  if (file.size > MAX_FILE_SIZE_BYTES)
    return `File exceeds ${MAX_FILE_SIZE_MB} MB limit (${formatBytes(file.size)}).`;
  const ext = getExt(file.name);
  if (ext && !ALLOWED_EXTENSIONS.includes(ext))
    return `File type "${ext}" is not supported.`;
  return null;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function ScanningProgress({ filename }: { filename: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-8">
      <div
        className="w-16 h-16 rounded-full border-2 flex items-center justify-center"
        style={{
          borderColor: "rgba(0,212,255,0.15)",
          borderTopColor: "#00d4ff",
          animation: "spin-slow 1s linear infinite",
        }}
      >
        <span className="text-xl" style={{ animation: "none" }}>👻</span>
      </div>
      <div className="text-center">
        <p className="text-sm font-semibold text-white">Scanning…</p>
        <p className="text-xs mt-1 max-w-xs truncate" style={{ color: "#94a3b8" }}>
          {filename}
        </p>
      </div>
      <div className="w-52 h-1 rounded-full overflow-hidden" style={{ background: "#1a2744" }}>
        <div
          className="h-full rounded-full"
          style={{
            background: "linear-gradient(90deg, #00d4ff, #0089b2)",
            animation: "data-flow 1.5s ease-in-out infinite",
            backgroundSize: "200% 100%",
          }}
        />
      </div>
      <div className="flex gap-4 text-xs" style={{ color: "#475569" }}>
        <span>✓ DLP Rules</span>
        <span className="animate-pulse" style={{ color: "#00d4ff" }}>◉ ML Classifier</span>
        <span style={{ color: "#334155" }}>◯ Risk Engine</span>
      </div>
    </div>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, { bg: string; text: string }> = {
    CRITICAL: { bg: "rgba(239,68,68,0.12)", text: "#ef4444" },
    HIGH:     { bg: "rgba(249,115,22,0.12)", text: "#f97316" },
    MEDIUM:   { bg: "rgba(234,179,8,0.12)", text: "#eab308" },
    LOW:      { bg: "rgba(52,208,88,0.12)", text: "#34d058" },
  };
  const c = colors[severity?.toUpperCase()] ?? colors.LOW;
  return (
    <span
      className="text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase"
      style={{ background: c.bg, color: c.text }}
    >
      {severity || "LOW"}
    </span>
  );
}

function FileRow({
  qf,
  onRemove,
  onSelect,
  isSelected,
}: {
  qf: QueuedFile;
  onRemove: () => void;
  onSelect: () => void;
  isSelected: boolean;
}) {
  const statusIcon: Record<FileStatus, string> = {
    queued: "○",
    scanning: "◉",
    done: "✓",
    error: "✗",
  };
  const statusColor: Record<FileStatus, string> = {
    queued: "#475569",
    scanning: "#00d4ff",
    done: "#34d058",
    error: "#ef4444",
  };

  return (
    <div
      className="flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-all duration-150"
      style={{
        background: isSelected
          ? "rgba(0,212,255,0.06)"
          : "rgba(15,23,41,0.5)",
        border: isSelected
          ? "1px solid rgba(0,212,255,0.25)"
          : "1px solid transparent",
      }}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onSelect()}
      aria-label={`Select ${qf.file.name} to view result`}
      aria-pressed={isSelected}
    >
      {/* Status indicator */}
      <span
        className="text-sm font-bold shrink-0"
        style={{
          color: statusColor[qf.status],
          animation: qf.status === "scanning" ? "pulse 1s ease-in-out infinite" : "none",
        }}
      >
        {statusIcon[qf.status]}
      </span>

      {/* File info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-white truncate">{qf.file.name}</p>
        <p className="text-[11px]" style={{ color: "#475569" }}>
          {formatBytes(qf.file.size)}&nbsp;·&nbsp;{getExt(qf.file.name) || "file"}
          {qf.result && (
            <>
              &nbsp;·&nbsp;
              <span style={{ color: statusColor[qf.status] }}>
                {qf.result.findings.length} finding{qf.result.findings.length !== 1 ? "s" : ""}
              </span>
            </>
          )}
          {qf.error && (
            <>&nbsp;·&nbsp;<span style={{ color: "#ef4444" }}>{qf.error}</span></>
          )}
        </p>
      </div>

      {/* Severity badge */}
      {qf.result && (
        <SeverityBadge severity={qf.result.severity} />
      )}

      {/* Remove button (only when queued) */}
      {qf.status === "queued" && (
        <button
          type="button"
          className="shrink-0 flex items-center justify-center w-6 h-6 rounded transition-colors"
          style={{ color: "#475569" }}
          onClick={(e) => { e.stopPropagation(); onRemove(); }}
          aria-label={`Remove ${qf.file.name}`}
          title="Remove file"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
            <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </button>
      )}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
export default function ScannerPage() {
  const checked = useAuthGuard();
  const dropZoneId = useId();
  const inputRef = useRef<HTMLInputElement>(null);

  const [queue, setQueue] = useState<QueuedFile[]>([]);
  const [dragging, setDragging] = useState(false);
  const [running, setRunning] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [globalError, setGlobalError] = useState("");

  // ── File queue helpers ──────────────────────────────────────────────────────
  const addFiles = useCallback((files: FileList | File[]) => {
    setGlobalError("");
    const newEntries: QueuedFile[] = [];
    const errs: string[] = [];
    Array.from(files).forEach((f) => {
      const err = validateFile(f);
      if (err) {
        errs.push(`${f.name}: ${err}`);
        return;
      }
      // Deduplicate by name+size
      setQueue((prev) => {
        if (prev.some((q) => q.file.name === f.name && q.file.size === f.size)) return prev;
        return [...prev];
      });
      newEntries.push({
        id: `${f.name}-${f.size}-${Date.now()}`,
        file: f,
        status: "queued",
      });
    });
    if (newEntries.length) {
      setQueue((prev) => [...prev, ...newEntries]);
    }
    if (errs.length) {
      setGlobalError(errs.join("\n"));
    }
  }, []);

  const removeFile = useCallback((id: string) => {
    setQueue((prev) => prev.filter((q) => q.id !== id));
    setSelectedId((prev) => (prev === id ? null : prev));
  }, []);

  const clearAll = useCallback(() => {
    setQueue([]);
    setSelectedId(null);
    setGlobalError("");
  }, []);

  // ── Drag-and-drop handlers ──────────────────────────────────────────────────
  function onDragOver(e: React.DragEvent) {
    e.preventDefault();
    setDragging(true);
  }
  function onDragLeave() {
    setDragging(false);
  }
  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  }
  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files?.length) addFiles(e.target.files);
    e.target.value = "";
  }

  // ── Scan runner ─────────────────────────────────────────────────────────────
  async function runScans() {
    const toScan = queue.filter((q) => q.status === "queued");
    if (!toScan.length) return;
    setRunning(true);
    setGlobalError("");

    for (const entry of toScan) {
      // Mark as scanning
      setQueue((prev) =>
        prev.map((q) =>
          q.id === entry.id ? { ...q, status: "scanning" } : q
        )
      );
      setSelectedId(entry.id);

      try {
        const data = await scanFile(entry.file, {
          destination: "EXTERNAL",
          action: "UPLOAD",
          device_id: "WEB-CONSOLE",
          user: "web_analyst",
        });
        const result: ScanResultData = {
          filename: data.filename,
          file_hash: data.file_hash,
          classification: (data.classification ?? "INTERNAL") as ScanResultData["classification"],
          decision_score: data.decision_score ?? 0,
          risk_score: data.risk_score ?? 0,
          severity: data.severity ?? "LOW",
          action_taken: data.action_taken ?? "ALLOWED",
          findings: (data.findings ?? []).map((f) => ({
            rule_name: f.rule_name ?? f.rule ?? "UNKNOWN",
            category: f.category ?? "",
            severity: f.severity ?? "LOW",
            matches_count: f.matches_count ?? 0,
            sample_match: f.sample_match ?? f.matched_text,
          })),
          incident_id: data.incident_id,
          breakdown: data.breakdown as Record<string, number> | undefined,
        };
        setQueue((prev) =>
          prev.map((q) =>
            q.id === entry.id ? { ...q, status: "done", result } : q
          )
        );
      } catch (err) {
        const msg =
          err instanceof Error
            ? err.message
            : "Scan failed. Ensure the backend is running.";
        setQueue((prev) =>
          prev.map((q) =>
            q.id === entry.id ? { ...q, status: "error", error: msg } : q
          )
        );
      }
    }

    setRunning(false);
  }

  // ── Demo scan ───────────────────────────────────────────────────────────────
  async function runDemoScan() {
    setRunning(true);
    setGlobalError("");

    const demoId = `demo-${Date.now()}`;
    const demoEntry: QueuedFile = {
      id: demoId,
      file: new File(
        ["Customer PAN: ABCDE1234F, Aadhaar: 1234 5678 9012, Email: test@example.com"],
        "demo_customer_data.txt",
        { type: "text/plain" }
      ),
      status: "scanning",
    };

    setQueue((prev) => [...prev, demoEntry]);
    setSelectedId(demoId);

    try {
      const data = await scanText({
        text: "Customer PAN: ABCDE1234F, Aadhaar: 1234 5678 9012, Email: test@example.com, Phone: 9876543210",
        filename: "demo_customer_data.txt",
        destination: "EXTERNAL",
        action: "UPLOAD",
        device_id: "WEB-CONSOLE",
        user: "web_analyst",
      });
      const result: ScanResultData = {
        filename: data.filename,
        file_hash: data.file_hash,
        classification: (data.classification ?? "INTERNAL") as ScanResultData["classification"],
        decision_score: data.decision_score ?? 0,
        risk_score: data.risk_score ?? 0,
        severity: data.severity ?? "LOW",
        action_taken: data.action_taken ?? "ALLOWED",
        findings: (data.findings ?? []).map((f) => ({
          rule_name: f.rule_name ?? f.rule ?? "UNKNOWN",
          category: f.category ?? "",
          severity: f.severity ?? "LOW",
          matches_count: f.matches_count ?? 0,
          sample_match: f.sample_match ?? f.matched_text,
        })),
        incident_id: data.incident_id,
        breakdown: data.breakdown as Record<string, number> | undefined,
      };
      setQueue((prev) =>
        prev.map((q) => (q.id === demoId ? { ...q, status: "done", result } : q))
      );
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : "Backend not connected. Please verify the backend server is running.";
      setQueue((prev) =>
        prev.map((q) => (q.id === demoId ? { ...q, status: "error", error: msg } : q))
      );
    } finally {
      setRunning(false);
    }
  }

  // ── Derived state ───────────────────────────────────────────────────────────
  const queuedCount = queue.filter((q) => q.status === "queued").length;
  const doneCount   = queue.filter((q) => q.status === "done").length;
  const errorCount  = queue.filter((q) => q.status === "error").length;
  const selected    = queue.find((q) => q.id === selectedId);

  // ── Auth guard ──────────────────────────────────────────────────────────────
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

        {/* ── Header ────────────────────────────────────────────────────────── */}
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
              className="md:hidden flex items-center justify-center w-8 h-8 rounded-lg"
              style={{ color: "#94a3b8", background: "rgba(26,39,68,0.5)", border: "1px solid #1a2744" }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M3 6h18M3 12h18M3 18h18" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
              </svg>
            </button>
            <div>
              <h1 className="text-lg font-bold text-white">File Scanner</h1>
              <p className="text-xs mt-0.5" style={{ color: "#94a3b8" }}>
                Scan files for sensitive data and leakage risk
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Summary stats */}
            {queue.length > 0 && (
              <div className="hidden sm:flex items-center gap-3 text-xs mr-3" style={{ color: "#475569" }}>
                <span>{queue.length} file{queue.length !== 1 ? "s" : ""}</span>
                {doneCount > 0 && <span style={{ color: "#34d058" }}>✓ {doneCount} done</span>}
                {errorCount > 0 && <span style={{ color: "#ef4444" }}>✗ {errorCount} error{errorCount !== 1 ? "s" : ""}</span>}
              </div>
            )}
            <button
              id="demo-scan-btn"
              onClick={runDemoScan}
              disabled={running}
              className="px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200"
              style={{
                background: "rgba(0,212,255,0.1)",
                border: "1px solid rgba(0,212,255,0.3)",
                color: "#00d4ff",
                cursor: running ? "not-allowed" : "pointer",
                opacity: running ? 0.5 : 1,
              }}
            >
              👻 Demo Scan
            </button>
          </div>
        </div>

        {/* ── Body ──────────────────────────────────────────────────────────── */}
        <div className="p-6 animate-fade-up">
          <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">

            {/* ── LEFT PANEL: upload + queue ────────────────────────────────── */}
            <div className="xl:col-span-2 space-y-4">

              {/* Drop zone */}
              <div
                id={`drop-zone-${dropZoneId}`}
                role="button"
                tabIndex={0}
                aria-label="Drop zone: drop files here or click to browse"
                className={`drop-zone p-8 flex flex-col items-center justify-center gap-3 text-center cursor-pointer transition-all duration-200 ${dragging ? "dragging" : ""}`}
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
                onDrop={onDrop}
                onClick={() => inputRef.current?.click()}
                onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
                style={{
                  minHeight: 160,
                  border: dragging
                    ? "2px dashed #00d4ff"
                    : "2px dashed rgba(0,212,255,0.2)",
                  background: dragging
                    ? "rgba(0,212,255,0.04)"
                    : "rgba(15,23,41,0.6)",
                  borderRadius: 16,
                }}
              >
                <input
                  ref={inputRef}
                  type="file"
                  multiple
                  className="hidden"
                  accept={ALLOWED_EXTENSIONS.join(",")}
                  onChange={onFileChange}
                  aria-label="File input"
                />
                <div
                  className="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl"
                  style={{
                    background: "rgba(0,212,255,0.06)",
                    border: "1px solid rgba(0,212,255,0.15)",
                  }}
                >
                  {dragging ? "📂" : "👻"}
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">
                    {dragging ? "Drop files to add" : "Drag & drop files here"}
                  </p>
                  <p className="text-xs mt-1" style={{ color: "#94a3b8" }}>
                    or <span style={{ color: "#00d4ff" }}>click to browse</span>
                  </p>
                  <p className="text-[11px] mt-2" style={{ color: "#334155" }}>
                    .txt .csv .json .pdf .env .py .js .zip .tar.gz · max {MAX_FILE_SIZE_MB} MB each
                  </p>
                </div>
              </div>

              {/* Validation error */}
              {globalError && (
                <div
                  className="px-4 py-3 rounded-lg text-xs whitespace-pre-wrap"
                  style={{
                    background: "rgba(239,68,68,0.06)",
                    border: "1px solid rgba(239,68,68,0.2)",
                    color: "#ef4444",
                  }}
                >
                  ⚠ {globalError}
                </div>
              )}

              {/* File queue */}
              {queue.length > 0 && (
                <div
                  className="rounded-xl overflow-hidden"
                  style={{ background: "#0f1729", border: "1px solid #1a2744" }}
                >
                  {/* Queue header */}
                  <div
                    className="flex items-center justify-between px-4 py-3"
                    style={{ borderBottom: "1px solid #1a2744" }}
                  >
                    <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: "#475569" }}>
                      Files ({queue.length})
                    </p>
                    {queuedCount > 0 && !running && (
                      <button
                        type="button"
                        className="text-xs"
                        style={{ color: "#475569" }}
                        onClick={clearAll}
                        aria-label="Clear all queued files"
                      >
                        Clear queued
                      </button>
                    )}
                  </div>

                  {/* File list */}
                  <div className="p-2 space-y-1 max-h-72 overflow-y-auto">
                    {queue.map((qf) => (
                      <FileRow
                        key={qf.id}
                        qf={qf}
                        onRemove={() => removeFile(qf.id)}
                        onSelect={() => setSelectedId(qf.id)}
                        isSelected={selectedId === qf.id}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* Scan pipeline info */}
              <div
                className="px-4 py-3 rounded-xl"
                style={{ background: "#0f1729", border: "1px solid #1a2744" }}
              >
                <p className="text-xs font-semibold mb-2 uppercase tracking-wide" style={{ color: "#475569" }}>
                  Scan Pipeline
                </p>
                <div className="flex flex-wrap gap-2">
                  {[
                    "✓ DLP Rules",
                    "✓ PII Detection",
                    "✓ ML Classifier",
                    "✓ Risk Engine",
                    "✓ Incident Logging",
                  ].map((f) => (
                    <span
                      key={f}
                      className="text-[11px] px-2 py-1 rounded"
                      style={{
                        background: "rgba(52,208,88,0.08)",
                        color: "#34d058",
                        border: "1px solid rgba(52,208,88,0.15)",
                      }}
                    >
                      {f}
                    </span>
                  ))}
                </div>
              </div>

              {/* Scan button */}
              <button
                id="run-scan-btn"
                onClick={runScans}
                disabled={running || queuedCount === 0}
                className="btn-primary w-full py-3 flex items-center justify-center gap-2 text-sm"
                style={{ opacity: running || queuedCount === 0 ? 0.5 : 1 }}
                aria-label={`Scan ${queuedCount} queued file${queuedCount !== 1 ? "s" : ""}`}
              >
                {running ? (
                  <>
                    <span className="spinner" style={{ width: 16, height: 16 }} />
                    Scanning…
                  </>
                ) : (
                  <>
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
                      <circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="2" />
                      <path d="M21 21l-4.35-4.35" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                    </svg>
                    {queuedCount > 0
                      ? `Scan ${queuedCount} File${queuedCount !== 1 ? "s" : ""}`
                      : "Add files to scan"}
                  </>
                )}
              </button>
            </div>

            {/* ── RIGHT PANEL: results ──────────────────────────────────────── */}
            <div className="xl:col-span-3 space-y-4">
              {selected?.status === "scanning" ? (
                <div
                  className="rounded-xl"
                  style={{ background: "#0f1729", border: "1px solid #1a2744" }}
                >
                  <ScanningProgress filename={selected.file.name} />
                </div>
              ) : selected?.status === "error" ? (
                <div
                  className="rounded-xl p-6"
                  style={{ background: "#0f1729", border: "1px solid rgba(239,68,68,0.2)" }}
                >
                  <p className="text-sm font-semibold mb-2" style={{ color: "#ef4444" }}>
                    ✗ Scan failed — {selected.file.name}
                  </p>
                  <p className="text-xs" style={{ color: "#94a3b8" }}>{selected.error}</p>
                </div>
              ) : selected?.result ? (
                <div>
                  {/* File context banner */}
                  <div
                    className="flex items-center justify-between px-4 py-2.5 mb-3 rounded-lg"
                    style={{ background: "#0f1729", border: "1px solid #1a2744" }}
                  >
                    <p className="text-xs font-medium text-white truncate">{selected.file.name}</p>
                    <span className="text-xs shrink-0 ml-2" style={{ color: "#475569" }}>
                      {formatBytes(selected.file.size)}
                    </span>
                  </div>
                  <ScanResult result={selected.result} loading={false} />
                </div>
              ) : (
                /* Empty state */
                <div
                  className="rounded-xl flex flex-col items-center justify-center gap-4 text-center"
                  style={{
                    background: "#0f1729",
                    border: "1px solid #1a2744",
                    minHeight: 320,
                  }}
                >
                  <div
                    className="w-16 h-16 rounded-2xl flex items-center justify-center text-2xl"
                    style={{ background: "rgba(0,212,255,0.04)", border: "1px solid rgba(0,212,255,0.1)" }}
                  >
                    🔍
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">No result selected</p>
                    <p className="text-xs mt-1" style={{ color: "#475569" }}>
                      Add files and run a scan, or click a file in the queue to view its result.
                    </p>
                  </div>
                  {queue.length === 0 && (
                    <button
                      type="button"
                      className="text-xs px-4 py-2 rounded-lg transition-all"
                      style={{
                        background: "rgba(0,212,255,0.08)",
                        border: "1px solid rgba(0,212,255,0.2)",
                        color: "#00d4ff",
                      }}
                      onClick={runDemoScan}
                      disabled={running}
                    >
                      👻 Try a demo scan
                    </button>
                  )}
                </div>
              )}

              {/* Batch summary (shown when multiple scans done) */}
              {doneCount > 1 && (
                <div
                  className="rounded-xl px-4 py-3"
                  style={{ background: "#0f1729", border: "1px solid #1a2744" }}
                >
                  <p className="text-xs font-semibold uppercase tracking-wide mb-3" style={{ color: "#475569" }}>
                    Batch Summary
                  </p>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {[
                      { label: "Files Scanned", value: doneCount, color: "#00d4ff" },
                      {
                        label: "With Findings",
                        value: queue.filter((q) => (q.result?.findings.length ?? 0) > 0).length,
                        color: "#eab308",
                      },
                      {
                        label: "Incidents",
                        value: queue.filter((q) => q.result?.incident_id).length,
                        color: "#f97316",
                      },
                      { label: "Errors", value: errorCount, color: "#ef4444" },
                    ].map(({ label, value, color }) => (
                      <div
                        key={label}
                        className="rounded-lg px-3 py-2 text-center"
                        style={{ background: "rgba(0,0,0,0.2)", border: "1px solid #1a2744" }}
                      >
                        <p className="text-xl font-bold" style={{ color }}>{value}</p>
                        <p className="text-[10px] mt-0.5 uppercase tracking-wide" style={{ color: "#475569" }}>
                          {label}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
