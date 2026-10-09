"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function EnrollRootPage() {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = code.trim().toUpperCase().replace(/\s/g, "");
    if (!trimmed) {
      setError("Please enter an enrollment code");
      return;
    }
    setError("");
    router.push(`/enroll/${trimmed}`);
  };

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center p-4"
      style={{ background: "linear-gradient(135deg, #040a17 0%, #0a0f1e 50%, #060d1f 100%)" }}
    >
      {/* Ambient glow */}
      <div
        className="fixed top-0 left-1/2 -translate-x-1/2 w-96 h-96 rounded-full pointer-events-none"
        style={{
          background: "radial-gradient(circle, rgba(0,212,255,0.04) 0%, transparent 70%)",
          filter: "blur(40px)",
        }}
      />

      <div
        className="w-full max-w-sm rounded-2xl shadow-2xl p-7 relative"
        style={{
          background: "rgba(10,15,30,0.95)",
          border: "1px solid #1a2744",
          backdropFilter: "blur(20px)",
        }}
      >
        {/* Top accent line */}
        <div
          className="absolute top-0 left-0 right-0 h-0.5 rounded-t-2xl"
          style={{ background: "linear-gradient(90deg, transparent, #00d4ff, transparent)" }}
        />

        {/* Logo */}
        <div className="flex flex-col items-center mb-6 gap-2">
          <div
            className="w-12 h-12 rounded-2xl flex items-center justify-center text-xl font-black mb-1"
            style={{ background: "linear-gradient(135deg, #0089b2, #00d4ff)", color: "#fff" }}
          >
            DG
          </div>
          <h1 className="text-white font-bold text-lg">DataGhost</h1>
          <p className="text-slate-400 text-sm">Device Enrollment</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label
              htmlFor="enroll-code"
              className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold"
            >
              Enrollment Code
            </label>
            <input
              id="enroll-code"
              type="text"
              autoComplete="off"
              autoFocus
              placeholder="e.g. 482913"
              value={code}
              onChange={(e) => { setCode(e.target.value); setError(""); }}
              className="w-full px-4 py-3 rounded-xl font-mono text-center text-white text-lg font-bold tracking-widest outline-none transition-all"
              style={{
                background: "rgba(0,212,255,0.05)",
                border: error ? "1px solid rgba(255,59,59,0.5)" : "1px solid rgba(0,212,255,0.2)",
                caretColor: "#00d4ff",
              }}
              onFocus={(e) => {
                e.target.style.border = "1px solid #00d4ff";
              }}
              onBlur={(e) => {
                e.target.style.border = error ? "1px solid rgba(255,59,59,0.5)" : "1px solid rgba(0,212,255,0.2)";
              }}
            />
            {error && (
              <p className="text-xs text-red-400">{error}</p>
            )}
          </div>

          <button
            type="submit"
            className="w-full py-3.5 rounded-xl font-semibold text-white text-sm transition-all hover:brightness-110 active:scale-95 shadow-lg"
            style={{
              background: "linear-gradient(135deg, #0089b2, #00d4ff)",
              border: "1px solid rgba(0,212,255,0.4)",
            }}
          >
            Enroll Device →
          </button>
        </form>

        <p className="text-center text-slate-500 text-xs mt-5">
          Ask your IT administrator for the enrollment code shown in the DataGhost dashboard.
        </p>
      </div>

      <p className="text-slate-600 text-xs mt-5">
        DataGhost DLP Platform · Secure Enrollment Portal
      </p>
    </div>
  );
}
