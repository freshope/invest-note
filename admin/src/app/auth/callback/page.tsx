"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { exchangeCodeForSession } from "@/lib/auth";

// OAuth 콜백: BE 가 일회용 code 를 ?code= 로 부착해 이 페이지로 리다이렉트한다.
// URL 에서 code 를 직접 읽어 PKCE verifier 와 함께 BE /auth/token 으로 교환한 뒤
// 성공 시 대시보드(/)·실패 시 로그인(/login/?error=oauth)으로 이동한다.
export default function AuthCallbackPage() {
  const router = useRouter();
  // ⚠️ once-guard: 일회용 code 는 single-use. React strict-mode(dev) 이중 effect/재렌더로
  // 두 번 교환하면 두 번째 401 → 로그인 실패. async 호출 전에 동기적으로 set 해 이중 invoke 차단.
  const exchangedRef = useRef(false);

  useEffect(() => {
    if (exchangedRef.current) return;
    exchangedRef.current = true;

    // useSearchParams 는 static export 에서 Suspense 필요 → window.location.search 로 직접 읽음.
    const code = new URLSearchParams(window.location.search).get("code");
    if (!code) {
      router.replace("/login/?error=oauth");
      return;
    }

    exchangeCodeForSession(code)
      .then(() => router.replace("/"))
      .catch(() => router.replace("/login/?error=oauth"));
  }, [router]);

  return (
    <div className="flex min-h-svh items-center justify-center bg-background">
      <p className="text-sm text-muted-foreground">로그인 처리 중...</p>
    </div>
  );
}
