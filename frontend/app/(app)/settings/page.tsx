"use client";

import { useState } from "react";
import TopBar from "../../../components/TopBar";
import { getApiBaseUrl } from "@/lib/auth";

export default function SettingsPage() {
  const [settings, setSettings] = useState({
    apiUrl: getApiBaseUrl() || (typeof window !== "undefined" ? `${window.location.origin}/api` : "/api (proxy)"),
    riskLow: 20, riskMedium: 50, riskHigh: 75,
    autoBlock: true, emailAlerts: true, auditLog: true,
    retentionDays: 90, maxFileSizeMb: 50,
  });
  const [saved, setSaved] = useState(false);

  function save() {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
    <div className="dg-card">
      <p className="text-sm font-semibold text-white mb-4 pb-3 border-b" style={{ borderColor: "rgba(99,179,237,0.08)" }}>
        {title}
      </p>
      <div className="space-y-4">{children}</div>
    </div>
  );

  const Row = ({ label, desc, children }: { label: string; desc?: string; children: React.ReactNode }) => (
    <div className="flex items-center justify-between gap-4">
      <div>
        <p className="text-sm" style={{ color: "#94a3b8" }}>{label}</p>
        {desc && <p className="text-[11px] mt-0.5" style={{ color: "#334155" }}>{desc}</p>}
      </div>
      {children}
    </div>
  );

  const Toggle = ({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) => (
    <div
      className="relative w-10 h-5 rounded-full cursor-pointer flex-shrink-0 transition-all"
      style={{ background: value ? "rgba(16,185,129,0.3)" : "rgba(15,23,42,0.8)" }}
      onClick={() => onChange(!value)}
    >
      <div
        className="absolute top-0.5 w-4 h-4 rounded-full transition-all"
        style={{ left: value ? "calc(100% - 18px)" : "2px", background: value ? "#10b981" : "#334155" }}
      />
    </div>
  );

  return (
    <div className="min-h-screen">
      <TopBar title="Settings" subtitle="DataGhost platform configuration">
        <button
          className={`btn-primary text-xs py-2 px-4 ${saved ? "opacity-80" : ""}`}
          onClick={save}
        >
          {saved ? "✓ Saved!" : "Save Changes"}
        </button>
      </TopBar>

      <div className="p-6 animate-fade-up space-y-4 max-w-2xl">
        <Section title="🔌 API Configuration">
          <Row label="Backend API URL" desc="DataGhost FastAPI backend endpoint">
            <input
              className="dg-input w-64"
              value={settings.apiUrl}
              onChange={(e) => setSettings({ ...settings, apiUrl: e.target.value })}
            />
          </Row>
        </Section>

        <Section title="⚖ Risk Score Thresholds">
          {([
            { label: "Low → Medium boundary", key: "riskLow", color: "#10b981" },
            { label: "Medium → High boundary", key: "riskMedium", color: "#f59e0b" },
            { label: "High → Critical boundary", key: "riskHigh", color: "#ef4444" },
          ] as const).map((r) => (
            <Row key={r.label} label={r.label} desc={`Current: ≥ ${settings[r.key]}`}>
              <div className="flex items-center gap-3">
                <input
                  type="range" min="0" max="100"
                  value={settings[r.key]}
                  className="w-32 dg-checkbox"
                  style={{ accentColor: r.color }}
                  onChange={(e) => setSettings({ ...settings, [r.key]: +e.target.value })}
                />
                <span className="font-mono text-sm w-8 text-right" style={{ color: r.color }}>
                  {settings[r.key]}
                </span>
              </div>
            </Row>
          ))}
          <div className="mt-2 flex h-2 rounded-full overflow-hidden">
            <div style={{ width: `${settings.riskLow}%`, background: "#10b981" }} />
            <div style={{ width: `${settings.riskMedium - settings.riskLow}%`, background: "#f59e0b" }} />
            <div style={{ width: `${settings.riskHigh - settings.riskMedium}%`, background: "#ef4444" }} />
            <div style={{ width: `${100 - settings.riskHigh}%`, background: "#dc2626" }} />
          </div>
          <div className="flex justify-between text-[10px] mt-1" style={{ color: "#334155" }}>
            <span>LOW</span><span>MEDIUM</span><span>HIGH</span><span>CRITICAL</span>
          </div>
        </Section>

        <Section title="🛡 Response Settings">
          <Row label="Auto-block critical transfers" desc="Automatically block risk ≥ 76 events">
            <Toggle value={settings.autoBlock} onChange={(v) => setSettings({ ...settings, autoBlock: v })} />
          </Row>
          <Row label="Email alerts" desc="Send alerts to security team on HIGH/CRITICAL">
            <Toggle value={settings.emailAlerts} onChange={(v) => setSettings({ ...settings, emailAlerts: v })} />
          </Row>
          <Row label="Audit logging" desc="Record all events to the audit log">
            <Toggle value={settings.auditLog} onChange={(v) => setSettings({ ...settings, auditLog: v })} />
          </Row>
        </Section>

        <Section title="🗄 Data Retention">
          <Row label="Log retention (days)" desc="Automatically purge logs older than N days">
            <input
              type="number" min={7} max={365}
              className="dg-input w-24 text-right font-mono"
              value={settings.retentionDays}
              onChange={(e) => setSettings({ ...settings, retentionDays: +e.target.value })}
            />
          </Row>
          <Row label="Max scan file size (MB)" desc="Files larger than this are skipped">
            <input
              type="number" min={1} max={500}
              className="dg-input w-24 text-right font-mono"
              value={settings.maxFileSizeMb}
              onChange={(e) => setSettings({ ...settings, maxFileSizeMb: +e.target.value })}
            />
          </Row>
        </Section>

        {/* Version info */}
        <div
          className="px-4 py-3 rounded-lg"
          style={{ background: "rgba(15,23,42,0.5)", border: "1px solid rgba(99,179,237,0.06)" }}
        >
          <div className="grid grid-cols-3 gap-4 text-xs">
            {[
              { label: "DataGhost Version", value: "1.0.0" },
              { label: "Backend", value: "FastAPI + Python 3.11" },
              { label: "ML Engine", value: "scikit-learn + TF-IDF" },
            ].map((i) => (
              <div key={i.label}>
                <p style={{ color: "#334155" }}>{i.label}</p>
                <p className="font-mono mt-0.5" style={{ color: "#475569" }}>{i.value}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
