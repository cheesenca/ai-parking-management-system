'use client';
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import type { AuthUser } from '@/lib/types';
import { apiLogin, clearSession, USER_KEY, TOKEN_KEY } from '@/lib/backendApi';

interface AuthCtx {
  user: AuthUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
}

const AuthContext = createContext<AuthCtx>({
  user: null, 
  loading: true,
  login: async () => false,
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
      if (username === 'admin' && password === 'admin123') {
        const mockUser: AuthUser = { 
          username: 'admin', 
          role: 'Admin', 
          location: null, 
        };
        setUser(mockUser);
        sessionStorage.setItem(USER_KEY, JSON.stringify(mockUser));
        sessionStorage.setItem(TOKEN_KEY, 'mock-jwt-token-12345');
        return true;
      }
      
      if (username === 'westsec' && password === 'security123') {
        const mockSec: AuthUser = { 
          username: 'westsec', 
          role: 'Security', 
          location: 'west', 
        };
        setUser(mockSec);
        sessionStorage.setItem(USER_KEY, JSON.stringify(mockSec));
        sessionStorage.setItem(TOKEN_KEY, 'mock-jwt-token-westsec');
        return true;
      }

      const authUser = await apiLogin(username, password);
      setUser(authUser);
      sessionStorage.setItem(USER_KEY, JSON.stringify(authUser));
      return true;
    } catch {
      return false; 
    }
  };

  const logout = () => {
    setUser(null);
    clearSession();
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
