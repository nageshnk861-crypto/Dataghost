"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../../../lib/auth";
import TopBar from "../../../components/TopBar";

interface Incident {
  incident_id: string;
  timestamp: string;
  user: string;
  filename: string;
  classification: string;
  risk_score: number;
  severity: string;
  action_taken: string;
  destination: string;
}

function riskColor(r: number) {
  if (r >= 76) return "#ef4444";
  if (r >= 51) return "#f59e0b";
  if (r >= 21) return "#60a5fa";
  return "#10b981";
}

export default function EventsPage() {
  const [events, setEvents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const res = await apiFetch("/api/incidents?per_page=100");
        if (res.ok) {
          const data = await res.json();
          setEvents(data.items ?? []);
        }
      } finally {
        setLoading(false);
      }
    }
    load();
    const iv = setInterval(load, 15_000);
    return () => clearInterval(iv);
  }, []);

  function groupByDay(evts: Incident[]) {
    const groups: Record<string, Incident[]> = {};
    evts.forEach((e) => {
      const day = new Date(e.timestamp).toLocaleDateString([], {
        weekday: "long", month: "long", day: "numeric",
      });
      if (!groups[day]) groups[day] = [];
      groups[day].push(e);
    });
    return groups;
  }

  const groups = groupByDay(events);

  const counts = {
    critical: events.filter((e) => e.severity === "CRITICAL").length,
    high: events.filter((e) => e.severity === "HIGH").length,
    blocked: events.filter((e) => e.action_taken === "BLOCKED").length,
    total: events.length,
  };

  return (
    <div className="min-h-screen">
      <TopBar title="Security Events" subtitle="Live feed of all data transfer events">
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs font-medium" style={{ color: "#34d399" }}>LIVE · 15s refresh</span>
        </div>
      </TopBar>

      <div className="p-6 animate-fade-up">
        {/* Summary bar */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          {[
            { label: "Total Events", value: counts.total, color: "#94a3b8" },
            { label: "Critical", value: counts.critical, color: "#ef4444" },
            { label: "High Severity", value: counts.high, color: "#f59e0b" },
            { label: "Blocked", value: counts.blocked, color: "#ef4444" },
          ].map((s) => (
            <div key={s.label} className="stat-card flex items-center gap-3">
              <div className="w-2 h-8 rounded-full" style={{ background: s.color + "40", border: `1px solid ${s.color}60` }} />
              <div>
                <p className="text-[11px]" style={{ color: "#475569" }}>{s.label}</p>
                <p className="text-xl font-bold" style={{ color: s.color }}>{s.value}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Event timeline */}
        {loading ? (
          <div className="flex items-center justify-center h-48 gap-3">
            <div className="spinner" />
            <span className="text-sm" style={{ color: "#475569" }}>Loading events…</span>
          </div>
        ) : (
          <div className="space-y-6">
            {Object.entries(groups).map(([day, dayEvents]) => (
              <div key={day}>
                <div className="flex items-center gap-3 mb-3">
                  <p className="text-xs font-semibold" style={{ color: "#334155" }}>{day}</p>
                  <div className="flex-1 h-px" style={{ background: "rgba(99,179,237,0.06)" }} />
                  <span className="text-[11px]" style={{ color: "#1e3a5f" }}>{dayEvents.length} events</span>
                </div>

                <div className="space-y-2">
                  {dayEvents.map((e) => {
                    const color = riskColor(e.risk_score);
                    const isCritical = e.severity === "CRITICAL";
                    const isBlocked = e.action_taken === "BLOCKED";
                    return (
                      <div
                        key={e.incident_id}
                        className={`flex items-center gap-4 px-4 py-3 rounded-lg transition-all cursor-default ${
                          isCritical ? "alert-critical" : isBlocked ? "alert-high" : ""
                        }`}
                        style={{
                          background: isCritical
                            ? "rgba(239,68,68,0.05)"
                            : "rgba(13,21,38,0.6)",
                          border: `1px solid ${isCritical ? "rgba(239,68,68,0.15)" : "rgba(99,179,237,0.06)"}`,
                        }}
                      >
                        {/* Time */}
                        <span
                          className="font-mono text-[10px] flex-shrink-0 w-14 text-right"
                          style={{ color: "#334155" }}
                        >
                          {new Date(e.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </span>

                        {/* Dot */}
                        <div
                          className="w-2 h-2 rounded-full flex-shrink-0"
                          style={{ background: color, boxShadow: isCritical ? `0 0 6px ${color}` : "none" }}
                        />

                        {/* Content */}
                        <div className="flex-1 min-w-0 flex items-center gap-3 flex-wrap">
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded flex-shrink-0 badge-${e.action_taken.toLowerCase()}`}
                          >
                            {e.action_taken}
                          </span>
                          <span className="text-xs text-white font-medium truncate flex-1" title={e.filename}>
                            {e.filename}
                          </span>
                          <span className="font-mono text-[10px] flex-shrink-0" style={{ color: "#475569" }}>
                            {e.user}
                          </span>
                        </div>

                        {/* Right meta */}
                        <div className="flex items-center gap-3 flex-shrink-0">
                          <span
                            className={`text-[10px] px-2 py-0.5 rounded badge-${e.classification.toLowerCase()}`}
                          >
                            {e.classification}
                          </span>
                          <span className="text-[10px]" style={{ color: "#334155" }}>→ {e.destination}</span>
                          <span
                            className="font-mono text-xs font-bold w-8 text-right"
                            style={{ color }}
                          >
                            {e.risk_score}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}

            {events.length === 0 && (
              <div className="flex flex-col items-center justify-center py-20" style={{ color: "#1e3a5f" }}>
                <span className="text-5xl mb-4">⚡</span>
                <p className="text-sm">No events yet. Start scanning files to generate events.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
