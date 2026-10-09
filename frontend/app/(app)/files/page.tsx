"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../../../lib/auth";
import TopBar from "../../../components/TopBar";

interface ScanLog {
  id: number;
  timestamp: string;
  filename: string;
  file_hash: string;
  classification: string;
  risk_score: number;
  findings_count: number;
  device_id: string;
}

function riskColor(r: number) {
  if (r >= 76) return "#ef4444";
  if (r >= 51) return "#f59e0b";
  if (r >= 21) return "#60a5fa";
  return "#10b981";
}

function fileIcon(name: string) {
  const ext = name?.split(".").pop()?.toLowerCase() ?? "";
  if (["xlsx", "csv"].includes(ext)) return "📊";
  if (["pdf"].includes(ext)) return "📄";
  if (["docx", "doc", "txt"].includes(ext)) return "📝";
  if (["env", "yaml", "json", "cfg"].includes(ext)) return "⚙";
  if (["zip", "tar", "gz"].includes(ext)) return "📦";
  if (["sql"].includes(ext)) return "🗄";
  if (["log"].includes(ext)) return "📋";
  return "📁";
}

export default function FilesPage() {
  const [incidents, setIncidents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [classFilter, setClassFilter] = useState("");

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const res = await apiFetch("/api/incidents?per_page=100");
        if (res.ok) {
          const data = await res.json();
          setIncidents(data.items ?? []);
        }
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const filtered = incidents.filter((i) => {
    const q = search.toLowerCase();
    const matchSearch = !q || i.filename?.toLowerCase().includes(q) || i.user?.toLowerCase().includes(q);
    const matchClass = !classFilter || i.classification === classFilter;
    return matchSearch && matchClass;
  });

  const stats = {
    total: incidents.length,
    restricted: incidents.filter((i) => i.classification === "RESTRICTED").length,
    confidential: incidents.filter((i) => i.classification === "CONFIDENTIAL").length,
    blocked: incidents.filter((i) => i.action_taken === "BLOCKED").length,
  };

  return (
    <div className="min-h-screen">
      <TopBar title="Scanned Files" subtitle="All files processed by the DataGhost scanner">
        <input
          id="files-search"
          className="dg-input w-44"
          placeholder="Search files…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="dg-select"
          value={classFilter}
          onChange={(e) => setClassFilter(e.target.value)}
        >
          <option value="">All Classifications</option>
          <option value="RESTRICTED">Restricted</option>
          <option value="CONFIDENTIAL">Confidential</option>
          <option value="INTERNAL">Internal</option>
          <option value="PUBLIC">Public</option>
        </select>
      </TopBar>

      <div className="p-6 animate-fade-up">
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          {[
            { label: "Total Files", value: stats.total, color: "#94a3b8" },
            { label: "Restricted", value: stats.restricted, color: "#ef4444" },
            { label: "Confidential", value: stats.confidential, color: "#f59e0b" },
            { label: "Blocked", value: stats.blocked, color: "#ef4444" },
          ].map((s) => (
            <div key={s.label} className="stat-card">
              <p className="text-[11px] uppercase tracking-wide" style={{ color: "#475569" }}>{s.label}</p>
              <p className="text-2xl font-bold mt-1" style={{ color: s.color }}>{s.value}</p>
            </div>
          ))}
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-48 gap-3">
            <div className="spinner" />
            <span className="text-sm" style={{ color: "#475569" }}>Loading files…</span>
          </div>
        ) : (
          <div className="dg-card p-0 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full data-table">
                <thead>
                  <tr>
                    <th>File</th>
                    <th>Classification</th>
                    <th>Risk Score</th>
                    <th>Findings</th>
                    <th>Action</th>
                    <th>User</th>
                    <th>Device</th>
                    <th>Destination</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((f) => (
                    <tr key={f.incident_id}>
                      <td>
                        <div className="flex items-center gap-2">
                          <span className="text-base flex-shrink-0">{fileIcon(f.filename)}</span>
                          <span
                            className="text-xs truncate max-w-[160px] font-medium"
                            style={{ color: "#e2e8f0" }}
                            title={f.filename}
                          >
                            {f.filename}
                          </span>
                        </div>
                      </td>
                      <td>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-semibold badge-${f.classification?.toLowerCase()}`}>
                          {f.classification}
                        </span>
                      </td>
                      <td>
                        <div className="flex items-center gap-2">
                          <div className="w-12 h-1.5 rounded-full" style={{ background: "rgba(30,58,95,0.5)" }}>
                            <div
                              className="h-1.5 rounded-full"
                              style={{ width: `${f.risk_score}%`, background: riskColor(f.risk_score) }}
                            />
                          </div>
                          <span className="font-mono text-xs" style={{ color: riskColor(f.risk_score) }}>
                            {f.risk_score}
                          </span>
                        </div>
                      </td>
                      <td>
                        <span
                          className="font-mono text-xs"
                          style={{ color: f.findings_count > 0 ? "#f59e0b" : "#334155" }}
                        >
                          {f.findings_count ?? "—"}
                        </span>
                      </td>
                      <td>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-semibold badge-${f.action_taken?.toLowerCase()}`}>
                          {f.action_taken}
                        </span>
                      </td>
                      <td>
                        <span className="font-mono text-[10px]" style={{ color: "#64748b" }}>{f.user}</span>
                      </td>
                      <td>
                        <span className="font-mono text-[10px]" style={{ color: "#475569" }}>{f.device_id}</span>
                      </td>
                      <td>
                        <span className="text-xs" style={{ color: "#334155" }}>{f.destination}</span>
                      </td>
                      <td>
                        <span className="font-mono text-[10px]" style={{ color: "#334155" }}>
                          {new Date(f.timestamp).toLocaleString([], {
                            month: "short", day: "2-digit",
                            hour: "2-digit", minute: "2-digit",
                          })}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {filtered.length === 0 && (
                <div className="flex flex-col items-center justify-center py-16" style={{ color: "#1e3a5f" }}>
                  <span className="text-4xl mb-3">📁</span>
                  <p className="text-sm">No files match your filter</p>
                </div>
              )}
            </div>

            {/* Footer */}
            <div
              className="px-4 py-2.5 border-t flex items-center justify-between"
              style={{ borderColor: "rgba(99,179,237,0.06)" }}
            >
              <span className="text-xs" style={{ color: "#334155" }}>
                Showing {filtered.length} of {incidents.length} files
              </span>
              <span className="text-[10px] font-mono" style={{ color: "#1e3a5f" }}>
                SHA-256 hashed · Audit logged
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
