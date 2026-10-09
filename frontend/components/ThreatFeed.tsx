"use client";

export interface ThreatItem {
  incident_id: string;
  filename: string;
  risk_score: number;
  severity: string;
  user: string;
  timestamp: string;
  action_taken: string;
  // Legacy backend fields (kept for compatibility)
  label?: string;
  score?: number;
}

interface ThreatFeedProps {
  threats?: ThreatItem[];
}

function timeAgo(iso: string): string {
  if (!iso) return "—";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function severityDotColor(severity: string): string {
  if (severity === "CRITICAL") return "#ff3b3b";
  if (severity === "HIGH") return "#ff9f0a";
  if (severity === "MEDIUM") return "#60a5fa";
  return "#34d058";
}

function riskColor(score: number): string {
  if (score >= 80) return "#ff3b3b";
  if (score >= 60) return "#ff9f0a";
  if (score >= 30) return "#60a5fa";
  return "#34d058";
}

function ActionBadge({ action }: { action: string }) {
  const cfg: Record<string, { bg: string; color: string }> = {
    BLOCKED: { bg: "rgba(255,59,59,0.15)", color: "#ff3b3b" },
    ALERTED: { bg: "rgba(255,159,10,0.15)", color: "#ff9f0a" },
    ALLOWED: { bg: "rgba(52,208,88,0.15)", color: "#34d058" },
  };
  const c = cfg[action] ?? cfg.ALLOWED;
  return (
    <span
      className="text-[10px] font-bold px-2 py-0.5 rounded"
      style={{ background: c.bg, color: c.color, border: `1px solid ${c.color}30` }}
    >
      {action}
    </span>
  );
}

export default function ThreatFeed({ threats }: ThreatFeedProps) {
  const items = threats ?? [];

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-6 gap-2">
        <span className="text-2xl">✅</span>
        <p className="text-sm" style={{ color: "#34d058" }}>
          No recent threats detected
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {items.map((t, idx) => {
        // Support both backend field shapes (label/score legacy, and full fields)
        const filename = t.filename || t.label || "—";
        const score = t.risk_score ?? t.score ?? 0;
        const user = t.user || "—";
        const timestamp = t.timestamp || "";
        const action = t.action_taken || "—";
        const dotColor = severityDotColor(t.severity);
        const key = t.incident_id || `threat-${idx}`;

        return (
          <div
            key={key}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors"
            style={{
              background: "rgba(15,23,42,0.6)",
              border: `1px solid ${dotColor}15`,
            }}
          >
            {/* Severity dot */}
            <span
              className="w-2 h-2 rounded-full flex-shrink-0"
              style={{
                background: dotColor,
                boxShadow: `0 0 6px ${dotColor}`,
              }}
            />

            {/* File + user */}
            <div className="flex-1 min-w-0">
              <p
                className="text-xs font-semibold truncate"
                style={{ color: "#e2e8f0" }}
                title={filename}
              >
                {filename}
              </p>
              <p className="text-[10px] mt-0.5" style={{ color: "#475569" }}>
                <span className="font-mono" style={{ color: "#94a3b8" }}>{user}</span>
                <span className="mx-1">·</span>
                {timeAgo(timestamp)}
              </p>
            </div>

            {/* Risk score */}
            <span
              className="font-mono text-sm font-bold flex-shrink-0"
              style={{ color: riskColor(score), minWidth: "2rem", textAlign: "right" }}
            >
              {score}
            </span>

            {/* Action badge */}
            <ActionBadge action={action} />
          </div>
        );
      })}
    </div>
  );
}
