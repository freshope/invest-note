"use client";

import { useEffect, useRef } from "react";
import { useAuth } from "./AuthProvider";
import { identifyUser, resetUser } from "@/lib/analytics";

/**
 * Supabase 인증 상태 → PostHog 유저 식별 브리지.
 * AuthProvider 를 Supabase 전용으로 유지하기 위해 식별 로직을 분리한다.
 * user.id 변화 시에만 identify/reset (prevId 가드로 중복 호출 방지).
 */
export function PostHogIdentifyBridge() {
  const { user } = useAuth();
  const prevId = useRef<string | null>(null);

  useEffect(() => {
    const id = user?.id ?? null;
    if (id === prevId.current) return;
    prevId.current = id;
    if (id) identifyUser(id);
    else resetUser();
  }, [user]);

  return null;
}
