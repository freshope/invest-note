"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { exchangeCodeForSession } from "@/lib/auth";
import { FullPageSpinner } from "@/components/base/FullPageSpinner";
import { LOGIN_OAUTH_FAILED_PATH_WITH_SLASH } from "@/lib/auth/errors";

// 웹 BE flow OAuth 콜백(개발 편의용). BE 가 일회용 code 를 ?code= 로 부착해 이 페이지로
// 302 redirect 한다. URL 에서 code 를 읽어 PKCE verifier 와 함께 BE /auth/token 으로 교환한 뒤
// 성공 시 "/"·실패 시 /login/?error=oauth_failed 로 이동한다(어드민 콜백 미러링).
// 네이티브 OAuth 완료는 딥링크→CapacitorDeepLinkHandler 경로라 이 페이지를 거치지 않는다.
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
      router.replace(LOGIN_OAUTH_FAILED_PATH_WITH_SLASH);
      return;
    }

    exchangeCodeForSession(code)
      .then(() => router.replace("/"))
      .catch(() => router.replace(LOGIN_OAUTH_FAILED_PATH_WITH_SLASH));
  }, [router]);

  return <FullPageSpinner />;
}
