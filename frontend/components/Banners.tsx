"use client";

/**
 * DataGhost – shared alert banner components.
 *
 * <WakeUpBanner onRetry={fn} />   – amber "Backend waking up" notice with auto-retry countdown
 * <ErrorBanner message={...} onRetry={fn} />  – red error banner
 */

import { useEffect, useState } from "react";

// ── WakeUpBanner ──────────────────────────────────────────────────────────────

interface WakeUpBannerProps {
  onRetry: () => void;
}

export function WakeUpBanner({ onRetry }: WakeUpBannerProps) {
  const [countdown, setCountdown] = useState(30);

  // Auto-retry after countdown reaches 0
  useEffect(() => {
    if (countdown <= 0) {
      onRetry();
      return;
    }
    const t = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [countdown, onRetry]);

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
      <div className="flex items-center gap-2 min-w-0">
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
        <span className="min-w-0">
          <strong>Backend is waking up</strong> — Render free-tier sleeps after inactivity.
          Usually takes <strong>15–40 seconds</strong>. Auto-retrying in{" "}
          <strong style={{ color: "#f59e0b" }}>{countdown}s</strong>…
        </span>
      </div>
      <button
        onClick={() => { setCountdown(30); onRetry(); }}
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
  // If the message looks like a cold-start error, render the friendlier banner
  const looksLikeWakeUp =
    message.toLowerCase().includes("waking up") ||
    message.toLowerCase().includes("starting up") ||
    message.toLowerCase().includes("cold start") ||
    message.toLowerCase().includes("502") ||
    message.toLowerCase().includes("backend unavailable") ||
    message.toLowerCase().includes("failed to fetch");

  if (looksLikeWakeUp && onRetry) {
    return <WakeUpBanner onRetry={onRetry} />;
  }

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
