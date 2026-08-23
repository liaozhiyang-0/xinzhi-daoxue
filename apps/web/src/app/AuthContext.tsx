import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError } from "../api/client.js";
import { createGuestSession, getCurrentPrincipal, logout } from "../api/auth.js";
import type { CurrentPrincipal } from "../api/auth.js";

export interface AuthIdentity {
  userId: string;
  role: string;
  displayName: string;
  authenticated: boolean;
  guest: boolean;
  source: CurrentPrincipal;
}

interface AuthContextValue {
  identity: AuthIdentity | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function normalize(principal: CurrentPrincipal): AuthIdentity {
  const isGuest = principal.guest === true || principal.role === "guest";
  return {
    userId: isGuest ? principal.user_id : principal.id,
    role: principal.role || (isGuest ? "guest" : "student"),
    displayName: isGuest ? (principal.display_name || "游客") : (principal.display_name || principal.login),
    authenticated: !isGuest,
    guest: isGuest,
    source: principal,
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [identity, setIdentity] = useState<AuthIdentity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      let principal: CurrentPrincipal;
      try {
        principal = await getCurrentPrincipal();
      } catch (reason) {
        if (!(reason instanceof ApiError) || reason.status !== 401) throw reason;
        principal = await createGuestSession();
      }
      setIdentity(normalize(principal));
    } catch (reason) {
      setIdentity(null);
      setError(reason instanceof Error ? reason.message : "身份状态暂时无法读取");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void refresh(); }, []);

  async function signOut() {
    await logout().catch(() => undefined);
    await refresh();
  }

  const value = useMemo<AuthContextValue>(
    () => ({ identity, loading, error, refresh, signOut }),
    [identity, loading, error],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
