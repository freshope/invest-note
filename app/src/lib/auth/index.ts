// Provider-neutral auth 인터페이스. 외부(컴포넌트·lib/api·페이지)는 이 모듈만 사용한다.
// @supabase/supabase-js 의 결합은 supabase-client.ts 뒤에 격리되어 있다.
import { getSupabaseClient } from "./supabase-client";
import type { AuthUser, AuthChangeCallback } from "./types";

export type { AuthUser, AuthChangeCallback } from "./types";

function toAuthUser(
  user: { id: string; email?: string } | null | undefined,
): AuthUser | null {
  if (!user) return null;
  return { id: user.id, email: user.email ?? null };
}

type OAuthProvider = "google" | "kakao" | "apple";

/**
 * OAuth 로그인 시작. 네이티브는 skipBrowserRedirect=true 로 받은 `url` 을
 * 인앱 브라우저(Browser.open)에 직접 먹여야 하므로 반드시 url 을 반환한다.
 */
export async function signInWithOAuth(
  provider: OAuthProvider,
  options: { redirectTo: string; skipBrowserRedirect: boolean },
): Promise<{ url: string | null }> {
  const { data, error } = await getSupabaseClient().auth.signInWithOAuth({
    provider,
    options: {
      redirectTo: options.redirectTo,
      skipBrowserRedirect: options.skipBrowserRedirect,
    },
  });
  if (error) throw error;
  return { url: data?.url ?? null };
}

/** 현재 세션의 access token(Bearer 주입용). 없으면 null. */
export async function getAccessToken(): Promise<string | null> {
  try {
    const {
      data: { session },
    } = await getSupabaseClient().auth.getSession();
    return session?.access_token ?? null;
  } catch {
    return null;
  }
}

/** 현재 로그인 사용자(provider-neutral). 없으면 null. */
export async function getUser(): Promise<AuthUser | null> {
  try {
    const {
      data: { session },
    } = await getSupabaseClient().auth.getSession();
    return toAuthUser(session?.user);
  } catch {
    return null;
  }
}

/** 로그아웃. 서버 호출 실패에도 로컬 세션은 무조건 비우도록 scope: "local" 고정. */
export async function signOut(): Promise<void> {
  await getSupabaseClient().auth.signOut({ scope: "local" });
}

/** 인증 상태 변화 구독. 해제 함수를 반환한다. */
export function subscribe(callback: AuthChangeCallback): () => void {
  const {
    data: { subscription },
  } = getSupabaseClient().auth.onAuthStateChange((_event, session) => {
    callback(toAuthUser(session?.user));
  });
  return () => subscription.unsubscribe();
}

/** implicit flow: access/refresh 토큰으로 세션 설정. 실패 시 throw(딥링크 핸들러 라우팅용). */
export async function setSession(
  accessToken: string,
  refreshToken: string,
): Promise<void> {
  const { error } = await getSupabaseClient().auth.setSession({
    access_token: accessToken,
    refresh_token: refreshToken,
  });
  if (error) throw error;
}

/** PKCE flow: 인가 code 를 세션으로 교환. 실패 시 throw(딥링크 핸들러 라우팅용). */
export async function exchangeCodeForSession(code: string): Promise<void> {
  const { error } = await getSupabaseClient().auth.exchangeCodeForSession(code);
  if (error) throw error;
}
