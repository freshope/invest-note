"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getUser, subscribe, type AuthUser } from "@/lib/auth";
import { ensureBeAuthFlagLoaded } from "@/lib/api/app-config";
import { isNativePlatform } from "@/lib/platform";

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
}

const AuthContext = createContext<AuthContextValue>({ user: null, loading: true });

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    let unsubscribe = () => {};

    const applyUser = (next: AuthUser | null) => {
      // TOKEN_REFRESHED 등 같은 사용자 이벤트가 반복될 때 불필요한 re-render 방지
      setUser((prev) => {
        if (!prev || !next) return next;
        return prev.id === next.id ? prev : next;
      });
    };

    (async () => {
      // ⚠️ 2b-4 race fix: 네이티브는 auth flow 결정(isBeAuthFlow=isNativePlatform && beAuthEnabled)이
      // 비동기 app-config 에 의존한다. subscribe()/getUser() 는 1회 등록·조회이므로, 플래그 로드 전
      // (beAuthEnabled=false) 실행되면 Supabase 채널을 잡아 BE flow 로그인 emit 을 영영 못 받는다.
      // 플래그를 먼저 resolve(세션 고정)한 뒤 초기화한다. ensureBeAuthFlagLoaded 는 bounded(timeout)
      // 라 오프라인에서도 hang 하지 않는다. 웹은 isBeAuthFlow 가 항상 false 라 대기 불필요.
      if (isNativePlatform()) {
        await ensureBeAuthFlagLoaded();
        if (!mounted) return;
      }

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

      unsubscribe = subscribe((u) => {
        applyUser(u);
        setLoading(false);
      });
    })();

    return () => {
      mounted = false;
      unsubscribe();
    };
  }, []);

  const value = useMemo<AuthContextValue>(() => ({ user, loading }), [user, loading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
