import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import * as authApi from "../api/auth";
import { tokenStore } from "../api/client";

interface AuthContextValue {
  user: authApi.User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<authApi.User | null>(null);
  const [loading, setLoading] = useState(true);

  async function refreshUser() {
    if (!tokenStore.getAccess()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await authApi.fetchCurrentUser();
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshUser();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleLogin(email: string, password: string) {
    await authApi.login(email, password);
    await refreshUser();
  }

  async function handleRegister(email: string, password: string, fullName?: string) {
    await authApi.register(email, password, fullName);
    await refreshUser();
  }

  function handleLogout() {
    authApi.logout();
    setUser(null);
  }

  return (
    <AuthContext.Provider
      value={{ user, loading, login: handleLogin, register: handleRegister, logout: handleLogout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
