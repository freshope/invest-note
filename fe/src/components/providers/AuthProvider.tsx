"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { User } from "@supabase/supabase-js";
import { createClient } from "@/lib/supabase/client";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
}

const AuthContext = createContext<AuthContextValue>({ user: null, loading: true });

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const supabase = createClient();
    let mounted = true;

    const applyUser = (next: User | null) => {
      // TOKEN_REFRESHED 등 같은 사용자 이벤트가 반복될 때 불필요한 re-render 방지
      setUser((prev) => {
        if (!prev || !next) return next;
        return prev.id === next.id ? prev : next;
      });
    };

    supabase.auth.getSession()
      .then(({ data: { session } }) => {
        if (!mounted) return;
        applyUser(session?.user ?? null);
        setLoading(false);
      })
      .catch(() => {
        if (!mounted) return;
        applyUser(null);
        setLoading(false);
      });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      applyUser(session?.user ?? null);
      setLoading(false);
    });

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, []);

  const value = useMemo<AuthContextValue>(() => ({ user, loading }), [user, loading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
