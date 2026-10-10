"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  signInWithRedirect,
  getRedirectResult,
  GoogleAuthProvider,
} from "firebase/auth";
import { auth } from "../../lib/firebase";
import { useAuthContext } from "../../lib/AuthContext";
import { API_BASE, getApiBaseUrl } from "../../lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { authReady, isAuthenticated, user, logout, setJwtAuth } = useAuthContext();

  const [input, setInput]       = useState("");
  const [password, setPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");

  // Helper to establish session with backend after Firebase auth succeeds
  async function completeFirebaseAuth(
    firebaseUser: { getIdToken: (force?: boolean) => Promise<string>; displayName?: string | null; email?: string | null },
    isRegistration = false
  ) {
    const defaultProfile = {
      username: firebaseUser.displayName || (firebaseUser.email ? firebaseUser.email.split("@")[0] : "Admin"),
      role: "admin",
    };

    if (typeof window !== "undefined") {
      localStorage.setItem("dg_user", JSON.stringify(defaultProfile));
    }

    // Attempt fast background profile sync without delaying dashboard navigation
    try {
      const idToken = await firebaseUser.getIdToken(false);
      const apiBase = getApiBaseUrl();
      const endpoint = isRegistration ? "/api/auth/register/firebase" : "/api/auth/me";
      const targetUrl = apiBase ? `${apiBase}${endpoint}` : endpoint;

      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 1800); // 1.8s timeout

      fetch(targetUrl, {
        method: isRegistration ? "POST" : "GET",
        headers: {
          Authorization: `Bearer ${idToken}`,
          "X-Tunnel-Skip-Anti-Phishing-Page": "true",
          "bypass-tunnel-reminder": "true",
          "Content-Type": "application/json",
        },
        signal: controller.signal,
      })
        .then((res) => (res.ok ? res.json() : null))
        .then((me) => {
          if (me && typeof window !== "undefined") {
            localStorage.setItem(
              "dg_user",
              JSON.stringify({ username: me.username || defaultProfile.username, role: me.role || defaultProfile.role })
            );
          }
        })
        .catch(() => {})
        .finally(() => clearTimeout(timer));
    } catch {
      // Non-fatal: Firebase user authentication succeeded
    }

    router.replace("/dashboard");
    return true;
  }

  // Handle redirect result on page load (for mobile Google sign-in redirect flow)
  useEffect(() => {
    if (!auth) return;
    let isMounted = true;

    getRedirectResult(auth)
      .then(async (result) => {
        if (!isMounted || !result || !result.user) return;
        setLoading(true);
        setError("");
        try {
          await completeFirebaseAuth(result.user, false);
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : "Google sign-in verification failed.";
          setError(msg.replace(/^Firebase:\s*/i, "").replace(/\s*\(auth\/[^)]+\)\.?$/, ""));
        } finally {
          if (isMounted) setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!isMounted) return;
        const msg = err instanceof Error ? err.message : "Google sign-in redirect failed.";
        setError(msg.replace(/^Firebase:\s*/i, "").replace(/\s*\(auth\/[^)]+\)\.?$/, ""));
      });

    return () => {
      isMounted = false;
    };
  }, [router]);

  // ── Google / Firebase sign-in ─────────────────────────────────────────────
  async function handleGoogleSignIn() {
    if (!auth) {
      setError("Firebase is not configured. Use username/password login.");
      return;
    }
    setLoading(true);
    setError("");

    const isMobile =
      typeof window !== "undefined" &&
      (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
        navigator.userAgent
      ) ||
        (window.matchMedia && window.matchMedia("(max-width: 768px)").matches));

    try {
      const provider = new GoogleAuthProvider();
      provider.setCustomParameters({ prompt: "select_account" });

      if (isMobile) {
        // Mobile browsers: Use Firebase-recommended redirect flow
        await signInWithRedirect(auth, provider);
        // Note: Execution stops here as the browser navigates to Google
        return;
      }

      // Desktop browsers: Use popup with fallback to redirect if popup is blocked
      try {
        const result = await signInWithPopup(auth, provider);
        const ok = await completeFirebaseAuth(result.user, false);
        if (!ok) {
          await result.user.delete().catch(() => {});
        }
      } catch (popupErr: unknown) {
        const pMsg = popupErr instanceof Error ? popupErr.message : String(popupErr);
        if (
          pMsg.includes("popup-blocked") ||
          pMsg.includes("popup-closed-by-user") ||
          pMsg.includes("cancelled-popup-request")
        ) {
          // Fallback to redirect if popup was blocked or closed
          await signInWithRedirect(auth, provider);
          return;
        }
        throw popupErr;
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Google sign-in failed.";
      setError(msg.replace(/^Firebase:\s*/i, "").replace(/\s*\(auth\/[^)]+\)\.?$/, ""));
    } finally {
      setLoading(false);
    }
  }

  // ── Form submit ───────────────────────────────────────────────────────────
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || !password.trim()) {
      setError("Please fill in all fields.");
      return;
    }
    setLoading(true);
    setError("");

    const isEmail = input.includes("@");

    // ── Path A: Firebase email/password ───────────────────────────────────
    if (auth && isEmail) {
      try {
        const cred = isSignUp
          ? await createUserWithEmailAndPassword(auth, input, password)
          : await signInWithEmailAndPassword(auth, input, password);

        const ok = await completeFirebaseAuth(cred.user, isSignUp);
        if (ok) return;
        setLoading(false);
        return;
      } catch (fbErr: unknown) {
        const msg = fbErr instanceof Error ? fbErr.message : String(fbErr);
        if (
          isSignUp ||
          (msg.includes("auth/") &&
            !msg.includes("auth/invalid-credential") &&
            !msg.includes("auth/user-not-found"))
        ) {
          setError(
            msg.replace(/^Firebase:\s*/i, "")
               .replace(/\s*\(auth\/[^)]+\)\.?$/, "")
          );
          setLoading(false);
          return;
        }
        // Fall through to DataGhost JWT ONLY for non-signup login errors.
      }
    }

    // ── Path B: DataGhost backend JWT (username OR email fallback) ────────
    const apiBase = getApiBaseUrl();
    const loginEndpoint = "/api/auth/login";
    const loginUrl = apiBase ? `${apiBase}${loginEndpoint}` : loginEndpoint;

    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 4000); // 4s timeout

      const res = await fetch(loginUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Tunnel-Skip-Anti-Phishing-Page": "true",
          "bypass-tunnel-reminder": "true",
        },
        body: JSON.stringify({ username: input.trim(), password }),
        signal: controller.signal,
      });
      clearTimeout(timer);

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const isDev = process.env.NODE_ENV !== "production";
        const devInfo = isDev ? ` [Target: ${loginUrl} | HTTP ${res.status}]` : "";
        setError((data.detail ?? "Invalid username or password.") + devInfo);
        return;
      }

      const data = await res.json();
      const access_token = data.access_token;

      // Extract profile or set sensible role
      const inferredRole = input.trim().toLowerCase().includes("admin") ? "admin" : "analyst";
      const userProfile = {
        username: data.user?.username || input.trim(),
        role: data.user?.role || inferredRole,
      };

      // Set JWT and session synchronously
      setJwtAuth(access_token, userProfile);

      // Navigate immediately to dashboard
      router.replace("/dashboard");
    } catch (err: unknown) {
      const targetDisplay = apiBase || (typeof window !== "undefined" ? window.location.origin : "server proxy");
      if (err instanceof Error && (err.name === "AbortError" || err.message.includes("abort"))) {
        setError("Login timed out. Please check your connection and try again.");
      } else if (err instanceof Error && (err.message.includes("fetch") || err.name === "TypeError")) {
        setError(
          `Cannot connect to DataGhost backend. Check that the backend server is accessible at ${targetDisplay}. (${err.message})`
        );
      } else {
        setError(`Login failed: ${err instanceof Error ? err.message : "Please check your connection and credentials."}`);
      }
    } finally {
      setLoading(false);
    }
  }

  // While Firebase initialises, show spinner (avoids flash of login form).
  if (!authReady) {
    return (
      <div className="flex items-center justify-center h-screen" style={{ background: "#030712" }}>
        <div className="spinner" />
      </div>
    );
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center relative overflow-hidden"
      style={{ background: "radial-gradient(ellipse at 60% 40%, #07132a 0%, #030712 60%)" }}
    >
      <div className="absolute inset-0 grid-pattern opacity-40" />
      <div className="absolute w-96 h-96 rounded-full opacity-10"
        style={{ background: "radial-gradient(circle, #0891b2, transparent)", top: "-80px", left: "-80px", filter: "blur(60px)" }} />
      <div className="absolute w-80 h-80 rounded-full opacity-10"
        style={{ background: "radial-gradient(circle, #7c3aed, transparent)", bottom: "-60px", right: "-60px", filter: "blur(60px)" }} />

      <div className="relative w-full max-w-sm mx-4 animate-fade-up"
        style={{ background: "rgba(10,15,30,0.92)", border: "1px solid rgba(6,182,212,0.15)", borderRadius: "16px",
          boxShadow: "0 0 60px rgba(6,182,212,0.06), 0 24px 48px rgba(0,0,0,0.5)", backdropFilter: "blur(20px)" }}>

        <div className="h-0.5 rounded-t-2xl"
          style={{ background: "linear-gradient(90deg, transparent, #06b6d4, #7c3aed, transparent)" }} />

        <div className="p-8">
          {/* Brand */}
          <div className="flex flex-col items-center mb-6">
            <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4 animate-pulse-glow"
              style={{ background: "linear-gradient(135deg, #0891b2 0%, #7c3aed 100%)" }}>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
                <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="#fff" strokeWidth="1.5" strokeLinejoin="round" />
                <path d="M2 17l10 5 10-5" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M2 12l10 5 10-5" stroke="rgba(255,255,255,0.5)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <h1 className="text-xl font-bold text-white glow-cyan">DataGhost</h1>
            <p className="text-xs mt-1" style={{ color: "#475569" }}>AI-Powered Data Loss Prevention</p>
          </div>

          {/* SOC badge */}
          <div className="flex items-center justify-center gap-2 mb-6 px-4 py-2 rounded-lg"
            style={{ background: "rgba(6,182,212,0.06)", border: "1px solid rgba(6,182,212,0.12)" }}>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs font-medium" style={{ color: "#94a3b8" }}>Security Operations Center</span>
          </div>

          {/* Active session banner if already logged in */}
          {isAuthenticated && (
            <div
              className="mb-5 p-3 rounded-xl flex items-center justify-between gap-3 animate-fade-in"
              style={{
                background: "rgba(6,182,212,0.08)",
                border: "1px solid rgba(6,182,212,0.25)",
              }}
            >
              <div className="min-w-0">
                <p className="text-xs text-slate-200">
                  Signed in as <span className="font-semibold text-cyan-400">{user?.username || "Active User"}</span>
                </p>
                <p className="text-[10px] text-slate-400 capitalize">{user?.role || "analyst"}</p>
              </div>
              <div className="flex items-center gap-1.5 flex-shrink-0">
                <button
                  type="button"
                  onClick={() => router.push("/dashboard")}
                  className="px-2.5 py-1 text-xs rounded-lg font-semibold transition-colors cursor-pointer"
                  style={{ background: "#06b6d4", color: "#030712" }}
                >
                  Dashboard →
                </button>
                <button
                  type="button"
                  onClick={() => void logout()}
                  className="px-2 py-1 text-xs rounded-lg transition-colors text-slate-400 hover:text-red-400 cursor-pointer"
                  style={{ background: "rgba(30,41,59,0.5)", border: "1px solid rgba(148,163,184,0.15)" }}
                >
                  Sign Out
                </button>
              </div>
            </div>
          )}

          {/* Google sign-in */}
          <button type="button" onClick={handleGoogleSignIn} disabled={loading}
            className="w-full flex items-center justify-center gap-3 py-2.5 px-4 mb-4 rounded-lg text-xs font-semibold transition-all"
            style={{ background: "rgba(30,41,59,0.6)", border: "1px solid rgba(148,163,184,0.15)",
              color: "#f1f5f9", opacity: loading ? 0.6 : 1, cursor: loading ? "not-allowed" : "pointer" }}>
            <svg width="16" height="16" viewBox="0 0 24 24">
              <path fill="#EA4335" d="M12 5c1.6 0 3 .6 4.1 1.6l3.1-3.1C17.3 1.8 14.8 1 12 1 7.4 1 3.5 3.6 1.6 7.4l3.7 2.9C6.2 7.1 8.9 5 12 5z" />
              <path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.6h6.5c-.3 1.5-1.1 2.8-2.4 3.7l3.7 2.9c2.2-2 3.7-5 3.7-8.9z" />
              <path fill="#FBBC05" d="M5.3 14.7c-.2-.7-.4-1.5-.4-2.7s.1-2 .4-2.7L1.6 6.4C.6 8.3 0 10.6 0 12s.6 3.7 1.6 5.6l3.7-2.9z" />
              <path fill="#34A853" d="M12 23c3.2 0 6-1.1 8-3l-3.7-2.9c-1.1.7-2.5 1.2-4.3 1.2-3.1 0-5.8-2.1-6.7-5.3L1.6 16c1.9 3.8 5.8 7 10.4 7z" />
            </svg>
            Continue with Google
          </button>

          <div className="flex items-center gap-3 my-4">
            <div className="flex-1 h-px bg-slate-800" />
            <span className="text-[10px] tracking-wider uppercase font-semibold text-slate-500">or username / email</span>
            <div className="flex-1 h-px bg-slate-800" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold mb-1.5 text-slate-400">EMAIL OR USERNAME</label>
              <input id="emailOrUsername" className="dg-input font-mono text-sm" type="text"
                placeholder="admin  or  user@example.com" autoComplete="username"
                value={input} onChange={(e) => setInput(e.target.value)} required />
            </div>
            <div>
              <label className="block text-xs font-semibold mb-1.5 text-slate-400">PASSWORD</label>
              <input id="password" className="dg-input font-mono text-sm" type="password"
                placeholder="••••••••" autoComplete="current-password"
                value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>

            {error && (
              <div className="px-3 py-2 rounded-lg text-xs font-medium"
                style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.25)", color: "#f87171" }}>
                ⚠ {error}
              </div>
            )}

            <button id="login-submit" type="submit"
              className="btn-primary w-full flex items-center justify-center gap-2 py-3 mt-2" disabled={loading}>
              {loading ? (
                <><span className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />Authenticating…</>
              ) : isSignUp ? "Create Account" : (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                    <path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4M10 17l5-5-5-5M15 12H3"
                      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  Secure Sign In
                </>
              )}
            </button>
          </form>

          <div className="mt-4 text-center">
            <button type="button" onClick={() => { setIsSignUp(!isSignUp); setError(""); }}
              className="text-xs text-cyan-400 hover:text-cyan-300 transition-colors"
              style={{ background: "none", border: "none", cursor: "pointer", fontFamily: "inherit" }}>
              {isSignUp ? "Already have an account? Sign In" : "New Firebase account? Register"}
            </button>
          </div>



          <p className="text-center text-[10px] mt-5" style={{ color: "#1e3a5f" }}>
            TLS Encrypted · RBAC Protected · Audit Logged
          </p>
        </div>
      </div>

      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 font-mono text-[10px]" style={{ color: "#1e293b" }}>
        DataGhost v1.0.0 · Final Year Project
      </div>
    </div>
  );
}
