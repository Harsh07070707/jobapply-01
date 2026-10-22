/**
 * AuthContext — token storage, auto-refresh, and helpers.
 *
 * Tokens are stored in localStorage so they survive page refreshes.
 * The access token is short-lived (15 min); the refresh token is
 * long-lived (7 days).  A proactive refresh fires 60 s before the
 * access token expires.  On any 401 from the API layer, the app
 * attempts one silent refresh then retries; if that fails it clears
 * credentials and redirects to /login.
 *
 * Usage:
 *   const { user, login, logout, accessToken } = useAuth();
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface AuthUser {
  user_id: string;
  email: string;
  status: string;
  email_verified: boolean;
}

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAccessToken: () => Promise<string | null>;
}

// ─── Storage keys ─────────────────────────────────────────────────────────────

const LS_ACCESS  = "ja_access";
const LS_REFRESH = "ja_refresh";
const LS_USER    = "ja_user";

// ─── JWT helpers (no external dep) ───────────────────────────────────────────

function jwtExp(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return typeof payload.exp === "number" ? payload.exp : null;
  } catch {
    return null;
  }
}

function isExpired(token: string): boolean {
  const exp = jwtExp(token);
  if (exp === null) return true;
  return Date.now() / 1000 >= exp - 10; // 10 s buffer
}

// ─── Context ──────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>(() => {
    const stored = localStorage.getItem(LS_USER);
    return {
      user:        stored ? (JSON.parse(stored) as AuthUser) : null,
      accessToken: localStorage.getItem(LS_ACCESS),
      isLoading:   false,
    };
  });

  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Internal: schedule proactive refresh ─────────────────────────────────
  const scheduleRefresh = useCallback((token: string) => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    const exp = jwtExp(token);
    if (!exp) return;
    const msUntilRefresh = Math.max(0, (exp - 60) * 1000 - Date.now());
    refreshTimerRef.current = setTimeout(() => {
      refreshAccessToken().catch(() => {/* handled inside */});
    }, msUntilRefresh);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Internal: call /api/auth/refresh ─────────────────────────────────────
  const refreshAccessToken = useCallback(async (): Promise<string | null> => {
    const raw = localStorage.getItem(LS_REFRESH);
    if (!raw) return null;
    try {
      const res = await fetch("/api/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: raw }),
      });
      if (!res.ok) throw new Error("refresh failed");
      const { access_token } = await res.json() as { access_token: string };
      localStorage.setItem(LS_ACCESS, access_token);
      setState(s => ({ ...s, accessToken: access_token }));
      scheduleRefresh(access_token);
      return access_token;
    } catch {
      // Refresh failed — clear everything
      localStorage.removeItem(LS_ACCESS);
      localStorage.removeItem(LS_REFRESH);
      localStorage.removeItem(LS_USER);
      setState({ user: null, accessToken: null, isLoading: false });
      return null;
    }
  }, [scheduleRefresh]);

  // ── On mount: check stored token validity, refresh if needed ─────────────
  useEffect(() => {
    const at = localStorage.getItem(LS_ACCESS);
    if (!at) return;
    if (isExpired(at)) {
      refreshAccessToken();
    } else {
      scheduleRefresh(at);
    }
    return () => {
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── login ─────────────────────────────────────────────────────────────────
  const login = useCallback(async (email: string, password: string) => {
    setState(s => ({ ...s, isLoading: true }));
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({})) as { detail?: string };
        throw new Error(err.detail ?? `Login failed (${res.status})`);
      }
      const data = await res.json() as { access_token: string; refresh_token: string };
      localStorage.setItem(LS_ACCESS, data.access_token);
      localStorage.setItem(LS_REFRESH, data.refresh_token);

      // Fetch user profile
      const meRes = await fetch("/api/auth/me", {
        headers: { Authorization: `Bearer ${data.access_token}` },
      });
      const user = meRes.ok ? await meRes.json() as AuthUser : null;
      if (user) localStorage.setItem(LS_USER, JSON.stringify(user));

      setState({ user, accessToken: data.access_token, isLoading: false });
      scheduleRefresh(data.access_token);
    } catch (err) {
      setState(s => ({ ...s, isLoading: false }));
      throw err;
    }
  }, [scheduleRefresh]);

  // ── logout ────────────────────────────────────────────────────────────────
  const logout = useCallback(async () => {
    const raw = localStorage.getItem(LS_REFRESH);
    if (raw) {
      fetch("/api/auth/logout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: raw }),
      }).catch(() => {/* fire-and-forget */});
    }
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    localStorage.removeItem(LS_ACCESS);
    localStorage.removeItem(LS_REFRESH);
    localStorage.removeItem(LS_USER);
    setState({ user: null, accessToken: null, isLoading: false });
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, login, logout, refreshAccessToken }),
    [state, login, logout, refreshAccessToken],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/** Returns only the current access token (refreshing silently if needed). */
export async function getValidToken(): Promise<string | null> {
  const at = localStorage.getItem(LS_ACCESS);
  if (!at) return null;
  if (!isExpired(at)) return at;
  // Attempt silent refresh
  const raw = localStorage.getItem(LS_REFRESH);
  if (!raw) return null;
  try {
    const res = await fetch("/api/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: raw }),
    });
    if (!res.ok) return null;
    const { access_token } = await res.json() as { access_token: string };
    localStorage.setItem(LS_ACCESS, access_token);
    return access_token;
  } catch {
    return null;
  }
}
