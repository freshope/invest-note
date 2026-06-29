"use client";

import { useEffect, useRef } from "react";
import { useAuth } from "./AuthProvider";
import { identifyUser, resetUser } from "@/lib/analytics";

/**
 * 인증 상태 → PostHog 유저 식별 브리지.
 * AuthProvider 의 책임을 식별 로직과 분리하기 위해 별도 컴포넌트로 둔다.
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
