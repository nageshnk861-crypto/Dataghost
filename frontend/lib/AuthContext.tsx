"use client";
/**
 * DataGhost â€“ Auth Context
 *
 * Tracks exactly ONE auth method at a time:
 *   "jwt"      â€“ signed in via DataGhost backend (username/password)
 *   "firebase" â€“ signed in via Firebase (email/Google)
 *   null       â€“ not authenticated
 *
 * Rules:
 *   â€¢ JWT path NEVER uses Firebase token for API calls.
 *   â€¢ Firebase path NEVER uses the localStorage JWT.
 *   â€¢ Logging in via username/password sets authMethod = "jwt" and removes
 *     any stale Firebase session, so the two paths never conflict.
 *   â€¢ isAuthenticated is React state â€” updates synchronously when auth changes.
 *   â€¢ The token getter registered with apiFetch returns the correct token for
 *     the current method and is never set to null (avoids null-window 401s).
 */

import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import {
  onAuthStateChanged,
  signOut,
  type User as FirebaseUser,
} from "firebase/auth";
import { auth } from "./firebase";
import {
  getJwt,
  saveJwt,
  saveUser,
  getSavedUser,
  removeJwt,
  setTokenGetter,
  fetchUserProfileFromBackend,
} from "./auth";

// â”€â”€ Types â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

type AuthMethod = "jwt" | "firebase" | null;

interface AuthUser {
  username: string;
  role: string;
}

interface AuthContextValue {
  /** Firebase init has completed (or Firebase is not configured). */
  authReady: boolean;
  /** The current auth method, or null if unauthenticated. */
  authMethod: AuthMethod;
  /** Shorthand: authMethod !== null */
  isAuthenticated: boolean;
  /** Current authenticated user profile */
  user: AuthUser | null;
  /** Returns a fresh token for the current auth method. */
  getAuthToken: () => Promise<string | null>;
  /**
   * Called after a successful DataGhost JWT login.
   * Stores the token and switches authMethod to "jwt".
   */
  setJwtAuth: (token: string, user: { username: string; role: string }) => void;
  /** Called when a 401 is received and the caller decides auth is invalid. */
  signalAuthFailure: () => void;
  /** Full sign-out. */
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// â”€â”€ Provider â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authReady, setAuthReady]       = useState(false);
  const [authMethod, setAuthMethod]     = useState<AuthMethod>(null);
  const [user, setUser]                 = useState<AuthUser | null>(null);
  const [firebaseUser, setFirebaseUser] = useState<FirebaseUser | null>(null);

  // Ref to firebase user so the token getter closure always has the latest
  // value without needing to re-register the getter on every FB user change.
  const firebaseUserRef = useRef<FirebaseUser | null>(null);
  firebaseUserRef.current = firebaseUser;

  // â”€â”€ Initialise on mount â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  useEffect(() => {
    // Check if a DataGhost JWT is already stored (e.g. after page refresh).
    const existingJwt = getJwt();
    const savedUser   = getSavedUser();
    if (existingJwt) {
      setAuthMethod("jwt");
      
      // Verify the role against the backend on startup
      // This ensures the stored role matches the current database role
      fetchUserProfileFromBackend(existingJwt).then((backendProfile) => {
        if (backendProfile) {
          setUser(backendProfile);
          saveUser(backendProfile);
        } else {
          // Backend unavailable or invalid token - clear session
          removeJwt();
          setAuthMethod(null);
          setUser(null);
        }
      }).catch(() => {
        // On error, keep the saved user temporarily
        if (savedUser) {
          setUser(savedUser);
        }
      });
      
      if (savedUser) {
        // Use saved user temporarily while verifying with backend
        setUser(savedUser);
      }
    }

    // Subscribe to Firebase auth state.
    if (!auth) {
      // Firebase not configured â€” ready immediately.
      if (!existingJwt) {
        setAuthMethod(null);
        setUser(null);
      }
      setAuthReady(true);
      return;
    }

    const unsub = onAuthStateChanged(auth, (fbUser) => {
      setFirebaseUser(fbUser);
      setAuthReady(true);

      // Only switch to firebase authMethod if there is NO DataGhost JWT.
      // A stored JWT always takes priority.
      if (!getJwt()) {
        setAuthMethod(fbUser ? "firebase" : null);
        if (fbUser) {
          const saved = getSavedUser();
          setUser(saved || { username: fbUser.email || "user", role: "analyst" });
        } else {
          setUser(null);
        }
      }
      // If there IS a JWT, we stay on "jwt" regardless of Firebase state.
    });

    return unsub;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Run once on mount.

  // â”€â”€ Token getter (registered once, never nulled) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  const getAuthToken = useCallback(async (): Promise<string | null> => {
    // JWT method: always read from localStorage (survives page refresh).
    const jwt = getJwt();
    if (jwt) return jwt;

    // Firebase method: get fresh token from current Firebase user.
    const fbUser = firebaseUserRef.current;
    if (fbUser) {
      try { return await fbUser.getIdToken(false); } catch { return null; }
    }

    return null;
  }, []); // Stable â€” uses refs and localStorage, not state.

  // Register once and never unregister (avoids null-window 401s).
  useEffect(() => {
    setTokenGetter(getAuthToken);
  }, [getAuthToken]);

  // â”€â”€ Public API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  /**
   * Called by the login page after a successful DataGhost JWT login.
   * Stores the token, updates auth state, and signs out of Firebase if needed
   * so the two auth methods never conflict.
   */
  const setJwtAuth = useCallback(
    (token: string, userProfile: { username: string; role: string }) => {
      saveJwt(token);
      saveUser(userProfile);
      setUser(userProfile);
      setAuthMethod("jwt");

      // Sign out of Firebase so getAuthToken never accidentally returns a
      // Firebase token for what is now a JWT session.
      if (auth && firebaseUserRef.current) {
        signOut(auth).catch(() => {});
        setFirebaseUser(null);
        firebaseUserRef.current = null;
      }
    },
    []
  );

  /**
   * Called by the dashboard (or any page) when it receives a definitive 401
   * and has decided the session is invalid. Clears auth state and redirects
   * to /login via soft navigation (no hard reload = no redirect loop).
   */
  const signalAuthFailure = useCallback(() => {
    removeJwt();
    setUser(null);
    setAuthMethod(null);
    if (auth && firebaseUserRef.current) {
      signOut(auth).catch(() => {});
      setFirebaseUser(null);
      firebaseUserRef.current = null;
    }
    // Use window.location ONCE here â€” this is the single, controlled redirect.
    // apiFetch never calls this; only a page that has confirmed the session is
    // dead calls signalAuthFailure.
    if (typeof window !== "undefined") {
      window.location.replace("/login");
    }
  }, []);

  const logout = useCallback(async () => {
    removeJwt();
    setUser(null);
    setAuthMethod(null);
    if (auth && firebaseUserRef.current) {
      try { await signOut(auth); } catch { /* ignore */ }
      setFirebaseUser(null);
      firebaseUserRef.current = null;
    }
    if (typeof window !== "undefined") {
      window.location.replace("/login");
    }
  }, []);

  const isAuthenticated = authMethod !== null;

  return (
    <AuthContext.Provider
      value={{
        authReady,
        authMethod,
        isAuthenticated,
        user,
        getAuthToken,
        setJwtAuth,
        signalAuthFailure,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// â”€â”€ Hook â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

export function useAuthContext(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuthContext must be inside <AuthProvider>");
  return ctx;
}

export const useAuth = useAuthContext;

// â”€â”€ Convenience re-exports for the login page â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export { saveJwt as storeJwt, saveUser as storeUser } from "./auth";


