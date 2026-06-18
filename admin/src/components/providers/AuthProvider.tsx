"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
// provider-neutral auth 인터페이스만 사용(@supabase/* 직접 import 금지 — 격리 경계).
import { getUser, subscribe, type AdminUser } from "@/lib/auth";

interface AuthContextValue {
  user: AdminUser | null;
  loading: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AdminUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    const applyUser = (next: AdminUser | null) => {
      // 같은 사용자 이벤트 반복(TOKEN_REFRESHED 등) 시 불필요한 re-render 방지
      setUser((prev) => {
        if (!prev || !next) return next;
        return prev.id === next.id ? prev : next;
      });
    };

    getUser()
      .then((u) => {
        if (!mounted) return;
        applyUser(u);
        setLoading(false);
      })
      .catch(() => {
        if (!mounted) return;
        applyUser(null);
        setLoading(false);
      });

    const unsubscribe = subscribe((u) => {
      applyUser(u);
      setLoading(false);
    });

    return () => {
      mounted = false;
      unsubscribe();
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, loading }),
    [user, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
