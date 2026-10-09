"use client";

import React, { useState } from "react";
import ClassificationBadge from "./ClassificationBadge";
import type { IncidentRow } from "@/lib/api";

// Re-export for backward compatibility so callers can import from here too
export type { IncidentRow };

interface IncidentTableProps {
  incidents?: IncidentRow[];
  loading?: boolean;
  onStatusChange?: (incidentId: string, newStatus: string) => void;
  limit?: number;
}

function riskColor(score: number): string {
  if (score >= 80) return "#ff3b3b";
  if (score >= 60) return "#ff9f0a";
  if (score >= 30) return "#60a5fa";
  return "#34d058";
}

function SeverityBadge({ severity }: { severity: string }) {
  const cfg: Record<string, { bg: string; color: string }> = {
    CRITICAL: { bg: "rgba(255,59,59,0.12)", color: "#ff3b3b" },
    HIGH: { bg: "rgba(255,159,10,0.12)", color: "#ff9f0a" },
    MEDIUM: { bg: "rgba(96,165,250,0.12)", color: "#60a5fa" },
    LOW: { bg: "rgba(52,208,88,0.12)", color: "#34d058" },
  };
  const c = cfg[severity] ?? cfg.LOW;
  return (
    <span
      className="text-[10px] font-bold px-2 py-0.5 rounded"
      style={{ background: c.bg, color: c.color, border: `1px solid ${c.color}25` }}
    >
      {severity}
    </span>
  );
}

function ActionBadge({ action }: { action: string }) {
  const cfg: Record<string, { bg: string; color: string }> = {
    BLOCKED: { bg: "rgba(255,59,59,0.12)", color: "#ff3b3b" },
    ALERTED: { bg: "rgba(255,159,10,0.12)", color: "#ff9f0a" },
    ALLOWED: { bg: "rgba(52,208,88,0.12)", color: "#34d058" },
  };
  const c = cfg[action] ?? cfg.ALLOWED;
  return (
    <span
      className="text-[10px] font-bold px-2 py-0.5 rounded"
      style={{ background: c.bg, color: c.color, border: `1px solid ${c.color}25` }}
    >
      {action}
    </span>
  );
}

function timeAgo(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

const STATUS_OPTIONS = ["OPEN", "ACKNOWLEDGED", "RESOLVED"] as const;

export default function IncidentTable({
  incidents,
  loading,
  onStatusChange,
  limit,
}: IncidentTableProps) {
  const [expanded, setExpanded] = useState<string | null>(null);

  // Skeleton state while loading
  if (loading) {
    return (
      <div className="overflow-x-auto">
        <table className="w-full data-table">
          <thead>
            <tr>
              <th style={{ textAlign: "left" }}>Time</th>
              <th style={{ textAlign: "left" }}>User</th>
              <th style={{ textAlign: "left" }}>File</th>
              <th style={{ textAlign: "left" }}>Classification</th>
              <th style={{ textAlign: "right" }}>Risk</th>
              <th style={{ textAlign: "left" }}>Severity</th>
              <th style={{ textAlign: "left" }}>Action</th>
              {onStatusChange && <th style={{ textAlign: "left" }}>Status</th>}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 5 }).map((_, i) => (
              <tr key={i}>
                <td colSpan={onStatusChange ? 8 : 7}>
                  <div
                    className="h-4 w-full animate-pulse rounded"
                    style={{ background: "rgba(26,39,68,0.8)" }}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  const data = incidents ?? [];
  const rows = limit ? data.slice(0, limit) : data;

  if (rows.length === 0) {
    return (
      <div className="overflow-x-auto">
        <table className="w-full data-table">
          <thead>
            <tr>
              <th style={{ textAlign: "left" }}>Time</th>
              <th style={{ textAlign: "left" }}>User</th>
              <th style={{ textAlign: "left" }}>File</th>
              <th style={{ textAlign: "left" }}>Classification</th>
              <th style={{ textAlign: "right" }}>Risk</th>
              <th style={{ textAlign: "left" }}>Severity</th>
              <th style={{ textAlign: "left" }}>Action</th>
              {onStatusChange && <th style={{ textAlign: "left" }}>Status</th>}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td
                colSpan={onStatusChange ? 8 : 7}
                className="text-center py-8 text-sm"
                style={{ color: "#475569" }}
              >
                No incidents found
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full data-table">
        <thead>
          <tr>
            <th style={{ textAlign: "left" }}>Time</th>
            <th style={{ textAlign: "left" }}>User</th>
            <th style={{ textAlign: "left" }}>File</th>
            <th style={{ textAlign: "left" }}>Classification</th>
            <th style={{ textAlign: "right" }}>Risk</th>
            <th style={{ textAlign: "left" }}>Severity</th>
            <th style={{ textAlign: "left" }}>Action</th>
            {onStatusChange && <th style={{ textAlign: "left" }}>Status</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const isExpanded = expanded === row.incident_id;
            const colSpan = onStatusChange ? 8 : 7;
            return (
              <React.Fragment key={row.incident_id}>
                <tr
                  className="cursor-pointer transition-colors"
                  style={isExpanded ? { background: "rgba(0,212,255,0.03)" } : {}}
                  onClick={() => setExpanded(isExpanded ? null : row.incident_id)}
                >
                  <td>
                    <span className="font-mono text-[10px]" style={{ color: "#475569" }}>
                      {timeAgo(row.timestamp)}
                    </span>
                  </td>
                  <td>
                    <span className="font-mono text-xs" style={{ color: "#94a3b8" }}>
                      {row.user}
                    </span>
                  </td>
                  <td>
                    <div>
                      <p
                        className="text-xs font-medium truncate max-w-[160px]"
                        style={{ color: "#e2e8f0" }}
                        title={row.filename}
                      >
                        {row.filename}
                      </p>
                      <p className="font-mono text-[10px]" style={{ color: "#00d4ff" }}>
                        {row.incident_id}
                      </p>
                    </div>
                  </td>
                  <td>
                    <ClassificationBadge
                      classification={
                        row.classification as
                          | "PUBLIC"
                          | "INTERNAL"
                          | "CONFIDENTIAL"
                          | "RESTRICTED"
                      }
                    />
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <span
                      className="font-mono text-sm font-bold"
                      style={{ color: riskColor(row.risk_score) }}
                    >
                      {row.risk_score}
                    </span>
                  </td>
                  <td>
                    <SeverityBadge severity={row.severity} />
                  </td>
                  <td>
                    <ActionBadge action={row.action_taken} />
                  </td>
                  {onStatusChange && (
                    <td onClick={(e) => e.stopPropagation()}>
                      <select
                        className="dg-select text-[11px] py-0.5 px-1"
                        value={row.status ?? "OPEN"}
                        onChange={(e) => onStatusChange(row.incident_id, e.target.value)}
                      >
                        {STATUS_OPTIONS.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                    </td>
                  )}
                </tr>
                {isExpanded && (
                  <tr key={`${row.incident_id}-detail`}>
                    <td
                      colSpan={colSpan}
                      style={{
                        background: "rgba(15,23,42,0.8)",
                        borderLeft: `2px solid ${riskColor(row.risk_score)}`,
                        padding: "0.75rem 1rem",
                      }}
                    >
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                        <div>
                          <p
                            style={{
                              color: "#334155",
                              fontSize: "10px",
                              letterSpacing: "0.05em",
                            }}
                          >
                            INCIDENT ID
                          </p>
                          <p className="font-mono mt-0.5" style={{ color: "#00d4ff" }}>
                            {row.incident_id}
                          </p>
                        </div>
                        <div>
                          <p
                            style={{
                              color: "#334155",
                              fontSize: "10px",
                              letterSpacing: "0.05em",
                            }}
                          >
                            DESTINATION
                          </p>
                          <p className="mt-0.5" style={{ color: "#94a3b8" }}>
                            {row.destination ?? "—"}
                          </p>
                        </div>
                        <div>
                          <p
                            style={{
                              color: "#334155",
                              fontSize: "10px",
                              letterSpacing: "0.05em",
                            }}
                          >
                            DEVICE
                          </p>
                          <p className="font-mono mt-0.5" style={{ color: "#94a3b8" }}>
                            {row.device_id ?? "—"}
                          </p>
                        </div>
                        <div>
                          <p
                            style={{
                              color: "#334155",
                              fontSize: "10px",
                              letterSpacing: "0.05em",
                            }}
                          >
                            TIMESTAMP
                          </p>
                          <p className="mt-0.5" style={{ color: "#94a3b8" }}>
                            {new Date(row.timestamp).toLocaleString()}
                          </p>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
