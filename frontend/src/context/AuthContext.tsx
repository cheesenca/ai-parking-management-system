'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import type { AuthUser } from '@/types';
import {
  apiLogin,
  apiForgotPassword,
  clearSession,
  USER_KEY,
} from '@/lib/backendApi';

interface AuthCtx {
  user: AuthUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<boolean>;
  forgotPassword: (email: string, newPassword: string) => Promise<{ ok: boolean; message: string }>;
  logout: () => void;
}

const AuthContext = createContext<AuthCtx>({
  user: null,
  loading: true,
  login: async () => false,
  forgotPassword: async () => ({ ok: false, message: '' }),
  logout: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    try {
      const stored = sessionStorage.getItem(USER_KEY);
      if (stored) setUser(JSON.parse(stored));
    } catch {
      //
    }
    setLoading(false);
  }, []);

  const login = async (username: string, password: string): Promise<boolean> => {
    try {
      const authUser = await apiLogin(username, password);
      setUser(authUser);
      sessionStorage.setItem(USER_KEY, JSON.stringify(authUser));
      return true;
    } catch {
      return false;
    }
  };

  const forgotPassword = async (email: string, newPassword: string) => {
    try {
      const res = await apiForgotPassword(email, newPassword);
      return { ok: true, message: res.message };
    } catch (err) {
      return { ok: false, message: err instanceof Error ? err.message : 'Password Reset Failed' };
    }
  };

  const logout = () => {
    setUser(null);
    clearSession();
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, forgotPassword, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);