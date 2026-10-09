"use client";

import { useRef, useState } from "react";
import Sidebar, { toggleSidebar } from "../../components/Sidebar";
import ScanResult from "../../components/ScanResult";
import type { ScanResultData } from "../../components/ScanResult";
import { scanFile, scanText } from "@/lib/api";
import { useAuthGuard } from "@/lib/useAuthGuard";

// ─── Progress bar animation ───────────────────────────────────────────────────
function ScanningProgress({ filename }: { filename: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-5 py-10">
      {/* Ghost scanning animation */}
      <div
        className="w-20 h-20 rounded-full border-2 flex items-center justify-center"
        style={{
          borderColor: "rgba(0,212,255,0.15)",
          borderTopColor: "#00d4ff",
          animation: "spin-slow 1s linear infinite",
        }}
      >
        <span className="text-2xl" style={{ animation: "none" }}>
          👻
        </span>
      </div>
      <div className="text-center">
        <p className="text-sm font-semibold text-white">Scanning…</p>
        <p className="text-xs mt-1 max-w-xs truncate" style={{ color: "#94a3b8" }}>
          {filename}
        </p>
      </div>
      {/* Animated progress bar */}
      <div
        className="w-64 h-1 rounded-full overflow-hidden"
        style={{ background: "#1a2744" }}
      >
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
        <span className="animate-pulse" style={{ color: "#00d4ff" }}>
          ◉ ML Classifier
        </span>
        <span style={{ color: "#334155" }}>◯ Risk Engine</span>
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function ScannerPage() {
  const checked = useAuthGuard();

  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [result, setResult] = useState<ScanResultData | null>(null);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) {
      setFile(f);
      setResult(null);
      setError("");
    }
  }

  async function runScan() {
    if (!file) return;
    setError("");
    setResult(null);
    setScanning(true);

    try {
      const data = await scanFile(file, {
        destination: "EXTERNAL",
        action: "UPLOAD",
        device_id: "WEB-CONSOLE",
        user: "web_analyst",
      });
      setResult({
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
      });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Backend not connected. Please verify the backend server is running."
      );
    } finally {
      setScanning(false);
    }
  }

  async function runDemoScan() {
    setFile(null);
    setResult(null);
    setError("");
    setScanning(true);

    try {
      const data = await scanText({
        text: "Customer PAN: ABCDE1234F, Aadhaar: 1234 5678 9012, Email: test@example.com, Phone: 9876543210",
        filename: "demo_customer_data.txt",
        destination: "EXTERNAL",
        action: "UPLOAD",
        device_id: "WEB-CONSOLE",
        user: "web_analyst",
      });
      setResult({
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
      });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Backend not connected. Please verify the backend server is running."
      );
    } finally {
      setScanning(false);
    }
  }

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
            {/* Hamburger — mobile only */}
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
            <div>
              <h1 className="text-lg font-bold text-white">File Scanner</h1>
              <p className="text-xs mt-0.5" style={{ color: "#94a3b8" }}>
                Scan files for sensitive data and leakage risk
              </p>
            </div>
          </div>
          <button
            onClick={runDemoScan}
            disabled={scanning}
            className="px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200"
            style={{
              background: "rgba(0,212,255,0.1)",
              border: "1px solid rgba(0,212,255,0.3)",
              color: "#00d4ff",
              cursor: scanning ? "not-allowed" : "pointer",
              opacity: scanning ? 0.5 : 1,
            }}
          >
            👻 Scan Demo File
          </button>
        </div>

        <div className="p-6 animate-fade-up">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* ── Upload Panel ────────────────────────────────────────────────── */}
            <div className="space-y-4">
              {/* Drop zone */}
              <div
                className={`drop-zone p-10 flex flex-col items-center justify-center gap-4 text-center cursor-pointer ${
                  dragging ? "dragging" : ""
                }`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                onClick={() => inputRef.current?.click()}
              >
                <input
                  ref={inputRef}
                  type="file"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) {
                      setFile(f);
                      setResult(null);
                      setError("");
                    }
                  }}
                />
                <div
                  className="w-16 h-16 rounded-2xl flex items-center justify-center text-3xl"
                  style={{
                    background: "rgba(0,212,255,0.06)",
                    border: "1px solid rgba(0,212,255,0.15)",
                  }}
                >
                  👻
                </div>
                {file ? (
                  <>
                    <p className="text-sm font-semibold text-white">{file.name}</p>
                    <p className="text-xs" style={{ color: "#94a3b8" }}>
                      {(file.size / 1024).toFixed(1)} KB · Click to change
                    </p>
                  </>
                ) : (
                  <>
                    <p className="text-sm font-medium text-white">
                      Drop file here or click to browse
                    </p>
                    <p className="text-xs" style={{ color: "#94a3b8" }}>
                      Supports .txt .csv .json .pdf .docx .xlsx .log .env .py .js
                    </p>
                  </>
                )}
              </div>

              {/* Scan features */}
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
                onClick={runScan}
                disabled={scanning || !file}
                className="btn-primary w-full py-3 flex items-center justify-center gap-2 text-sm"
                style={{ opacity: scanning || !file ? 0.5 : 1 }}
              >
                {scanning ? (
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
                    Run DataGhost Scan
                  </>
                )}
              </button>

              {error && (
                <div
                  className="px-4 py-3 rounded-lg text-sm"
                  style={{
                    background: "rgba(255,59,59,0.06)",
                    border: "1px solid rgba(255,59,59,0.2)",
                    color: "#ff3b3b",
                  }}
                >
                  ⚠ {error}
                </div>
              )}
            </div>

            {/* ── Results Panel ────────────────────────────────────────────────── */}
            <div>
              {scanning ? (
                <div
                  className="rounded-xl"
                  style={{ background: "#0f1729", border: "1px solid #1a2744" }}
                >
                  <ScanningProgress filename={file?.name ?? "demo_customer_data.txt"} />
                </div>
              ) : (
                <ScanResult result={result} loading={false} />
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
