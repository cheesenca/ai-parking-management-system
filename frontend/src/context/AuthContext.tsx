'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import type { AuthUser } from '@/types';
import {
  apiLogin,
<<<<<<< HEAD
  apiForgotPassword,
=======
  apiRequestPasswordReset,
  apiConfirmPasswordReset,
>>>>>>> origin/master
  clearSession,
  USER_KEY,
} from '@/lib/backendApi';

interface AuthCtx {
  user: AuthUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<boolean>;
<<<<<<< HEAD
  forgotPassword: (email: string, newPassword: string) => Promise<{ ok: boolean; message: string }>;
=======
  requestPasswordReset: (email: string) => Promise<{ ok: boolean; message: string; token?: string }>;
  confirmPasswordReset: (email: string, token: string, newPassword: string) => Promise<{ ok: boolean; message: string }>;
>>>>>>> origin/master
  logout: () => void;
}

const AuthContext = createContext<AuthCtx>({
  user: null,
  loading: true,
  login: async () => false,
<<<<<<< HEAD
  forgotPassword: async () => ({ ok: false, message: '' }),
=======
  requestPasswordReset: async () => ({ ok: false, message: '' }),
  confirmPasswordReset: async () => ({ ok: false, message: '' }),
>>>>>>> origin/master
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

<<<<<<< HEAD
  const forgotPassword = async (email: string, newPassword: string) => {
    try {
      const res = await apiForgotPassword(email, newPassword);
=======
  const requestPasswordReset = async (email: string) => {
    try {
      const res = await apiRequestPasswordReset(email);
      return { ok: true, message: res.message, token: res.token };
    } catch (err) {
      return { ok: false, message: err instanceof Error ? err.message : 'Could not request password reset' };
    }
  };

  const confirmPasswordReset = async (email: string, token: string, newPassword: string) => {
    try {
      const res = await apiConfirmPasswordReset(email, token, newPassword);
>>>>>>> origin/master
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
<<<<<<< HEAD
    <AuthContext.Provider value={{ user, loading, login, forgotPassword, logout }}>
=======
    <AuthContext.Provider value={{ user, loading, login, requestPasswordReset, confirmPasswordReset, logout }}>
>>>>>>> origin/master
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);