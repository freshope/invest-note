"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/providers/AuthProvider";
import { registerPush } from "@/lib/push/registerPush";
import { requestNotificationOpen } from "@/lib/notification-deeplink";

/**
 * 푸시 알림 등록 마운트 지점(Phase 2, 게이트). 로그인(user) 후 네이티브에서만 registerPush 실행.
 * 웹/미지원 플랫폼은 registerPush 내부 가드로 no-op. 알림 탭 시 홈으로 이동 + 알림 패널 딥링크 신호.
 */
export function PushRegistration() {
  const { user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!user) return;
    void registerPush({
      onNotificationTap: () => {
        requestNotificationOpen();
        router.push("/");
      },
    });
  }, [user, router]);

  return null;
}
