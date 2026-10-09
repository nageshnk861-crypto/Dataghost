"use client";

import ClassificationBadge from "./ClassificationBadge";
import RiskGauge from "./RiskGauge";

export interface ScanFinding {
  rule_name: string;
  category: string;
  severity: string;
  matches_count: number;
  sample_match?: string;
}

export interface ScanResultData {
  filename: string;
  file_size?: number;
  file_hash?: string;
  classification: "PUBLIC" | "INTERNAL" | "CONFIDENTIAL" | "RESTRICTED";
  decision_score: number;
  risk_score: number;
  severity: string;
  action_taken: string;
  findings: ScanFinding[];
  incident_id?: string | null;
  breakdown?: Record<string, number>;
}

interface ScanResultProps {
  result: ScanResultData | null;
  loading: boolean;
}

function findingIcon(severity: string): string {
  if (severity === "CRITICAL" || severity === "HIGH") return "🔴";
  if (severity === "MEDIUM") return "🟠";
  return "🟡";
}

function ActionBanner({ action, riskScore }: { action: string; riskScore: number }) {
  const cfg: Record<string, { bg: string; border: string; color: string; label: string; icon: string }> = {
    BLOCKED: {
      bg: "rgba(255,59,59,0.1)",
      border: "#ff3b3b",
      color: "#ff3b3b",
      label: "TRANSFER BLOCKED",
      icon: "🚨",
    },
    ALERTED: {
      bg: "rgba(255,159,10,0.08)",
      border: "#ff9f0a",
      color: "#ff9f0a",
      label: "SECURITY ALERT RAISED",
      icon: "⚠️",
    },
    ALLOWED: {
      bg: "rgba(52,208,88,0.08)",
      border: "#34d058",
      color: "#34d058",
      label: "TRANSFER ALLOWED",
      icon: "✅",
    },
  };
  const c = cfg[action] ?? cfg.ALLOWED;
  return (
    <div
      className="rounded-xl p-4 flex items-center gap-4"
      style={{
        background: c.bg,
        border: `1px solid ${c.border}40`,
      }}
    >
      <span className="text-3xl">{c.icon}</span>
      <div>
        <p className="text-lg font-bold" style={{ color: c.color }}>
          {c.label}
        </p>
        <p className="text-xs mt-0.5" style={{ color: "#94a3b8" }}>
          Risk Score: {riskScore}/100
        </p>
      </div>
    </div>
  );
}

function SkeletonBlock({ h = "h-4", w = "w-full" }: { h?: string; w?: string }) {
  return (
    <div
      className={`${h} ${w} rounded animate-pulse`}
      style={{ background: "rgba(26,39,68,0.8)" }}
    />
  );
}

export default function ScanResult({ result, loading }: ScanResultProps) {
  if (loading) {
    return (
      <div className="space-y-4">
        {/* Skeleton loading */}
        <div
          className="rounded-xl p-5 space-y-3"
          style={{ background: "#0f1729", border: "1px solid #1a2744" }}
        >
          <SkeletonBlock h="h-6" w="w-48" />
          <SkeletonBlock h="h-4" w="w-64" />
          <div className="flex gap-3 mt-4">
            <SkeletonBlock h="h-8" w="w-24" />
            <SkeletonBlock h="h-8" w="w-32" />
          </div>
        </div>
        <div
          className="rounded-xl p-5 flex justify-center"
          style={{ background: "#0f1729", border: "1px solid #1a2744" }}
        >
          <div className="flex flex-col items-center gap-3">
            <div
              className="w-16 h-16 rounded-full border-2"
              style={{
                borderColor: "rgba(0,212,255,0.2)",
                borderTopColor: "#00d4ff",
                animation: "spin-slow 1s linear infinite",
              }}
            />
            <p className="text-sm" style={{ color: "#94a3b8" }}>
              Analyzing…
            </p>
          </div>
        </div>
        <div
          className="rounded-xl p-5 space-y-2"
          style={{ background: "#0f1729", border: "1px solid #1a2744" }}
        >
          {[1, 2, 3].map((i) => (
            <SkeletonBlock key={i} h="h-10" />
          ))}
        </div>
      </div>
    );
  }

  if (!result) {
    return (
      <div
        className="min-h-64 flex flex-col items-center justify-center rounded-xl gap-4"
        style={{ border: "1px dashed #1a2744", color: "#1a2744" }}
      >
        <svg
          width="48"
          height="48"
          viewBox="0 0 24 24"
          fill="none"
          style={{ color: "#1a2744" }}
        >
          <circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="1.5" />
          <path
            d="M21 21l-4.35-4.35"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
        <p className="text-sm" style={{ color: "#334155" }}>
          Scan results will appear here
        </p>
      </div>
    );
  }

  const { filename, file_size, file_hash, classification, decision_score, risk_score, action_taken, findings } =
    result;

  return (
    <div className="space-y-4">
      {/* Header: file info */}
      <div
        className="rounded-xl p-4 space-y-2"
        style={{ background: "#0f1729", border: "1px solid #1a2744" }}
      >
        <div className="flex items-center gap-3">
          <span className="text-2xl">📄</span>
          <div className="flex-1 min-w-0">
            <p
              className="text-sm font-bold truncate"
              style={{ color: "#e2e8f0" }}
              title={filename}
            >
              {filename}
            </p>
            {file_size !== undefined && (
              <p className="text-xs" style={{ color: "#475569" }}>
                {file_size < 1024
                  ? `${file_size} B`
                  : file_size < 1048576
                  ? `${(file_size / 1024).toFixed(1)} KB`
                  : `${(file_size / 1048576).toFixed(1)} MB`}
              </p>
            )}
          </div>
        </div>
        {file_hash && (
          <div
            className="px-3 py-2 rounded-lg"
            style={{ background: "rgba(15,23,42,0.6)", border: "1px solid #1a2744" }}
          >
            <p className="text-[10px] mb-0.5" style={{ color: "#334155" }}>
              SHA-256
            </p>
            <p
              className="font-mono text-[10px] break-all"
              style={{ color: "#475569" }}
            >
              {file_hash.slice(0, 32)}…
            </p>
          </div>
        )}
        <div className="flex items-center gap-3 flex-wrap">
          <ClassificationBadge
            classification={classification}
          />
          <span className="text-xs" style={{ color: "#475569" }}>
            decision score: {decision_score.toFixed(3)}
          </span>
          {result.incident_id && (
            <span className="font-mono text-xs" style={{ color: "#00d4ff" }}>
              {result.incident_id}
            </span>
          )}
        </div>
      </div>

      {/* Risk gauge */}
      <div
        className="rounded-xl p-4 flex flex-col items-center"
        style={{ background: "#0f1729", border: "1px solid #1a2744" }}
      >
        <RiskGauge score={risk_score} size={180} />
      </div>

      {/* Action banner */}
      <ActionBanner action={action_taken} riskScore={risk_score} />

      {/* Findings list */}
      <div
        className="rounded-xl p-4"
        style={{ background: "#0f1729", border: "1px solid #1a2744" }}
      >
        <p className="text-xs font-semibold mb-3 uppercase tracking-wide" style={{ color: "#475569" }}>
          Sensitive Findings · {findings.length} detected
        </p>
        {findings.length === 0 ? (
          <div className="flex items-center gap-2 text-sm" style={{ color: "#34d058" }}>
            <span>✓</span>
            <span>No sensitive patterns detected</span>
          </div>
        ) : (
          <div className="space-y-2">
            {findings.map((f, i) => (
              <div
                key={i}
                className="flex items-start justify-between gap-3 px-3 py-2.5 rounded-lg"
                style={{
                  background: "rgba(15,23,42,0.6)",
                  border: "1px solid #1a2744",
                }}
              >
                <div className="flex items-start gap-2 min-w-0">
                  <span className="text-sm flex-shrink-0">{findingIcon(f.severity)}</span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span
                        className="text-xs font-semibold"
                        style={{ color: "#e2e8f0" }}
                      >
                        {f.rule_name.replace(/_/g, " ")}
                      </span>
                      <span className="text-[10px]" style={{ color: "#475569" }}>
                        {f.category}
                      </span>
                    </div>
                    {f.sample_match && (
                      <p
                        className="font-mono text-[10px] mt-1 truncate"
                        style={{ color: "#475569" }}
                        title={f.sample_match}
                      >
                        {f.sample_match}
                      </p>
                    )}
                    <p className="text-[10px] mt-0.5" style={{ color: "#334155" }}>
                      {f.matches_count} match{f.matches_count !== 1 ? "es" : ""}
                    </p>
                  </div>
                </div>
                <span
                  className="flex-shrink-0 text-[10px] font-bold px-2 py-0.5 rounded"
                  style={{
                    background:
                      f.severity === "CRITICAL" || f.severity === "HIGH"
                        ? "rgba(255,59,59,0.12)"
                        : f.severity === "MEDIUM"
                        ? "rgba(255,159,10,0.12)"
                        : "rgba(52,208,88,0.12)",
                    color:
                      f.severity === "CRITICAL" || f.severity === "HIGH"
                        ? "#ff3b3b"
                        : f.severity === "MEDIUM"
                        ? "#ff9f0a"
                        : "#34d058",
                  }}
                >
                  {f.severity}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
