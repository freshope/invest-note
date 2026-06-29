import { exchangeCodeForSession } from "@/lib/auth";
import { LOGIN_OAUTH_FAILED_PATH_WITH_SLASH } from "@/lib/auth/errors";

type Router = { replace: (path: string) => void };

/**
 * 웹 콜백 페이지(auth/callback)와 네이티브 딥링크 핸들러(CapacitorDeepLinkHandler)가 공유하는
 * post-code 라우팅 단일 출처. code 가 없으면 실패 페이지로, 있으면 BE /auth/token 교환 후
 * 성공 시 "/"·실패 시 실패 페이지로 이동한다. 두 진입점은 code 출처(window.location.search vs
 * 딥링크 URL searchParams)만 다르므로, 라우팅이 바뀔 때 한쪽만 갱신돼 갈라지는 것을 막는다.
 */
export async function exchangeAndRoute(
  code: string | null,
  router: Router,
): Promise<void> {
  if (!code) {
    router.replace(LOGIN_OAUTH_FAILED_PATH_WITH_SLASH);
    return;
  }
  try {
    await exchangeCodeForSession(code);
    router.replace("/");
  } catch {
    router.replace(LOGIN_OAUTH_FAILED_PATH_WITH_SLASH);
  }
}
