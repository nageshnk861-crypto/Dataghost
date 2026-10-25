"use client";

/**
 * DataGhost – shared alert banner components.
 *
 * <WakeUpBanner onRetry={fn} />   – amber "Backend waking up" notice
 * <ErrorBanner message={...} onRetry={fn} />  – red error banner
 *
 * Both are drop-in replacements for the repeated inline error JSX
 * found across dashboard, analytics, incidents, findings, devices, etc.
 */

// ── WakeUpBanner ──────────────────────────────────────────────────────────────

interface WakeUpBannerProps {
  onRetry: () => void;
}

export function WakeUpBanner({ onRetry }: WakeUpBannerProps) {
  return (
    <div
      className="px-4 py-3 rounded-lg text-sm flex items-center justify-between gap-4"
      role="alert"
      style={{
        background: "rgba(245,158,11,0.07)",
        border:     "1px solid rgba(245,158,11,0.25)",
        color:      "#fbbf24",
      }}
    >
      <div className="flex items-center gap-2">
        {/* Spinner */}
        <svg
          style={{ width: 16, height: 16, flexShrink: 0, animation: "spin 1s linear infinite" }}
          viewBox="0 0 24 24"
          fill="none"
        >
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" opacity="0.25" />
          <path fill="currentColor" d="M4 12a8 8 0 018-8v8z" opacity="0.75" />
        </svg>
        <span>
          <strong>Backend is waking up</strong> — Render free-tier instances sleep after
          inactivity. This usually takes <strong>30–60 seconds</strong>. The page will
          refresh automatically.
        </span>
      </div>
      <button
        onClick={onRetry}
        className="shrink-0 text-xs font-semibold px-3 py-1.5 rounded-md"
        style={{
          background: "rgba(245,158,11,0.15)",
          border:     "1px solid rgba(245,158,11,0.3)",
          color:      "#fbbf24",
          cursor:     "pointer",
        }}
      >
        Retry now
      </button>
    </div>
  );
}

// ── ErrorBanner ───────────────────────────────────────────────────────────────

interface ErrorBannerProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorBanner({ message, onRetry }: ErrorBannerProps) {
  return (
    <div
      className="px-4 py-3 rounded-lg text-sm flex items-center justify-between gap-4"
      role="alert"
      style={{
        background: "rgba(255,59,59,0.06)",
        border:     "1px solid rgba(255,59,59,0.2)",
        color:      "#ff3b3b",
      }}
    >
      <span>⚠ {message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          className="shrink-0 text-xs font-semibold px-3 py-1.5 rounded-md"
          style={{
            background: "rgba(255,59,59,0.12)",
            border:     "1px solid rgba(255,59,59,0.3)",
            color:      "#ff3b3b",
            cursor:     "pointer",
          }}
        >
          Retry
        </button>
      )}
    </div>
  );
}
