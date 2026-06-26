"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
// provider-neutral auth 인터페이스만 사용(auth SDK 직접 import 금지 — 격리 경계).
import { getUser, subscribe, type AdminUser } from "@/lib/auth";
import { adminApi } from "@/lib/api";

interface AuthContextValue {
  user: AdminUser | null;
  loading: boolean;
  // 어드민(allowlist) 여부. null = 미확정(세션 없음 또는 프로브 진행 중).
  // 클라이언트는 ADMIN_EMAILS 를 모르므로 BE /admin/me(require_admin) 로만 판정한다.
  isAdmin: boolean | null;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  isAdmin: null,
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AdminUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);

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

  // user 가 바뀔 때마다 /admin/me 로 allowlist 여부 프로브. 200 → admin, 403/오류 → 비-admin.
  // user 식별자가 같으면(applyUser 가 prev 유지) 재프로브하지 않는다.
  useEffect(() => {
    if (!user) {
      setIsAdmin(null);
      return;
    }
    let mounted = true;
    setIsAdmin(null); // 프로브 진행 중
    adminApi
      .me()
      .then(() => mounted && setIsAdmin(true))
      .catch(() => mounted && setIsAdmin(false));
    return () => {
      mounted = false;
    };
  }, [user]);

  const value = useMemo<AuthContextValue>(
    () => ({ user, loading, isAdmin }),
    [user, loading, isAdmin],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
