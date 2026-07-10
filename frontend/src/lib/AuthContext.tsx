'use client';
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import type { AuthUser } from '@/lib/types';
import {
  apiLogin,
  apiRegister,
  apiForgotPassword,
  clearSession,
  USER_KEY,
} from '@/lib/backendApi';

interface RegisterData {
  username: string;
  email: string;
  password: string;
  role?: string;
  location?: string;
}

interface AuthCtx {
  user: AuthUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<boolean>;
  register: (data: RegisterData) => Promise<{ ok: boolean; message: string }>;
  forgotPassword: (email: string, newPassword: string) => Promise<{ ok: boolean; message: string }>;
  logout: () => void;
}

const AuthContext = createContext<AuthCtx>({
  user: null,
  loading: true,
  login: async () => false,
  register: async () => ({ ok: false, message: '' }),
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

  const register = async (data: RegisterData) => {
    try {
      const res = await apiRegister(data);
      return { ok: true, message: res.message };
    } catch (err) {
      return { ok: false, message: err instanceof Error ? err.message : 'Registrasi gagal' };
    }
  };

  const forgotPassword = async (email: string, newPassword: string) => {
    try {
      const res = await apiForgotPassword(email, newPassword);
      return { ok: true, message: res.message };
    } catch (err) {
      return { ok: false, message: err instanceof Error ? err.message : 'Gagal mereset password' };
    }
  };

  const logout = () => {
    setUser(null);
    clearSession();
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, forgotPassword, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
