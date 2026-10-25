"use client";

/**
 * AiExplainPanel – DataGhost AI Explanation Panel
 *
 * Drop this anywhere you have incident/scan context.
 * It calls POST /api/ai/explain and streams the explanation back.
 *
 * Usage:
 *   <AiExplainPanel
 *     filename="customers.csv"
 *     classification="CONFIDENTIAL"
 *     riskScore={94}
 *     severity="CRITICAL"
 *     actionTaken="BLOCKED"
 *     destination="External"
 *     user="employee01"
 *     findings={[{ category: "PII", severity: "HIGH", count: 1842 }]}
 *   />
 */

import { useState } from "react";
import { apiFetch } from "@/lib/auth";

export interface AiFinding {
  category: string;
  severity: string;
  count?: number;
  description?: string;
}

export interface AiExplainPanelProps {
  incidentId?: string;
  filename?: string;
  classification?: string;
  riskScore?: number;
  severity?: string;
  actionTaken?: string;
  destination?: string;
  user?: string;
  findings?: AiFinding[];
}

type State = "idle" | "loading" | "done" | "error";

export default function AiExplainPanel(props: AiExplainPanelProps) {
  const [state, setState]               = useState<State>("idle");
  const [explanation, setExplanation]   = useState<string>("");
  const [model, setModel]               = useState<string>("");
  const [ollamaUsed, setOllamaUsed]     = useState(false);
  const [errorMsg, setErrorMsg]         = useState<string>("");

  async function handleExplain() {
    setState("loading");
    setExplanation("");
    setErrorMsg("");

    try {
      const body = {
        incident_id:    props.incidentId,
        filename:       props.filename,
        classification: props.classification,
        risk_score:     props.riskScore,
        severity:       props.severity,
        action_taken:   props.actionTaken,
        destination:    props.destination,
        user:           props.user,
        findings: props.findings?.map((f) => ({
          category:    f.category,
          severity:    f.severity,
          count:       f.count ?? 1,
          description: f.description,
        })),
      };

      const res = await apiFetch("/api/ai/explain", {
        method: "POST",
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setExplanation(data.explanation ?? "");
      setModel(data.model ?? "unknown");
      setOllamaUsed(data.ollama_used ?? false);
      setState("done");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Unknown error");
      setState("error");
    }
  }

  // ── Styles (inline — no extra CSS dependencies) ───────────────────────────
  const card: React.CSSProperties = {
    background:   "rgba(15, 23, 42, 0.7)",
    border:       "1px solid rgba(139, 92, 246, 0.25)",
    borderRadius: "12px",
    padding:      "16px 20px",
    marginTop:    "12px",
  };

  const badge = (used: boolean): React.CSSProperties => ({
    display:       "inline-flex",
    alignItems:    "center",
    gap:           "4px",
    fontSize:      "11px",
    padding:       "2px 8px",
    borderRadius:  "6px",
    background:    used ? "rgba(139,92,246,0.12)" : "rgba(100,116,139,0.12)",
    border:        `1px solid ${used ? "rgba(139,92,246,0.3)" : "rgba(100,116,139,0.25)"}`,
    color:         used ? "#a78bfa" : "#94a3b8",
    marginLeft:    "8px",
  });

  return (
    <div style={card}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "18px" }}>🤖</span>
          <span style={{ fontWeight: 600, fontSize: "14px", color: "#e2e8f0" }}>
            AI Security Analyst
          </span>
          {state === "done" && (
            <span style={badge(ollamaUsed)}>
              {ollamaUsed ? "✦ Ollama" : "⟳ Rule-based"} · {model}
            </span>
          )}
        </div>

        {/* Action button */}
        {(state === "idle" || state === "error" || state === "done") && (
          <button
            onClick={handleExplain}
            style={{
              display:       "flex",
              alignItems:    "center",
              gap:           "6px",
              padding:       "6px 14px",
              borderRadius:  "8px",
              fontSize:      "13px",
              fontWeight:    600,
              cursor:        "pointer",
              border:        "1px solid rgba(139,92,246,0.4)",
              background:    state === "done"
                ? "rgba(139,92,246,0.06)"
                : "rgba(139,92,246,0.15)",
              color:         "#a78bfa",
              transition:    "all 0.15s",
            }}
          >
            <span>✦</span>
            {state === "done" ? "Re-explain" : "Why was this flagged?"}
          </button>
        )}
      </div>

      {/* States */}
      {state === "idle" && (
        <p style={{ fontSize: "13px", color: "#64748b", margin: 0 }}>
          Click <strong style={{ color: "#a78bfa" }}>Why was this flagged?</strong> to get an
          AI-generated security explanation for this event.
        </p>
      )}

      {state === "loading" && (
        <div style={{ display: "flex", alignItems: "center", gap: "10px", color: "#94a3b8" }}>
          <svg
            style={{ width: 18, height: 18, animation: "spin 1s linear infinite", flexShrink: 0 }}
            viewBox="0 0 24 24"
            fill="none"
          >
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" opacity="0.25" />
            <path fill="currentColor" d="M4 12a8 8 0 018-8v8z" opacity="0.75" />
          </svg>
          <span style={{ fontSize: "13px" }}>
            Analysing event with DataGhost AI…
          </span>
        </div>
      )}

      {state === "error" && (
        <div
          style={{
            fontSize:     "13px",
            color:        "#f87171",
            background:   "rgba(248,113,113,0.07)",
            border:       "1px solid rgba(248,113,113,0.2)",
            borderRadius: "8px",
            padding:      "10px 14px",
          }}
        >
          ⚠ {errorMsg}
        </div>
      )}

      {state === "done" && explanation && (
        <div
          style={{
            fontSize:     "14px",
            lineHeight:   1.7,
            color:        "#cbd5e1",
            borderLeft:   "3px solid rgba(139,92,246,0.4)",
            paddingLeft:  "14px",
            margin:       0,
          }}
        >
          {explanation.split("\n").filter(Boolean).map((line, i) => (
            <p key={i} style={{ margin: "0 0 8px" }}>{line}</p>
          ))}
        </div>
      )}
    </div>
  );
}
