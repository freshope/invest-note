// Provider-neutral auth 인터페이스. 외부(컴포넌트·lib/api·페이지)는 이 모듈만 사용한다.
// @supabase/supabase-js 의 결합은 supabase-client.ts 뒤에 격리되어 있다.
import { getSupabaseClient } from "./supabase-client";
import type { AdminUser, AuthChangeCallback } from "./types";

export type { AdminUser, AuthChangeCallback } from "./types";

function toAdminUser(
  user: { id: string; email?: string } | null | undefined,
): AdminUser | null {
  if (!user) return null;
  return { id: user.id, email: user.email ?? null };
}

/** 구글 OAuth 로그인 시작. 웹 전용(콜백 경로로 리다이렉트). */
export async function signInWithGoogle(redirectTo: string): Promise<void> {
  const { error } = await getSupabaseClient().auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo },
  });
  if (error) throw error;
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
export async function getUser(): Promise<AdminUser | null> {
  try {
    const {
      data: { session },
    } = await getSupabaseClient().auth.getSession();
    return toAdminUser(session?.user);
  } catch {
    return null;
  }
}

export async function signOut(): Promise<void> {
  await getSupabaseClient().auth.signOut();
}

/** 인증 상태 변화 구독. 해제 함수를 반환한다. */
export function subscribe(callback: AuthChangeCallback): () => void {
  const {
    data: { subscription },
  } = getSupabaseClient().auth.onAuthStateChange((_event, session) => {
    callback(toAdminUser(session?.user));
  });
  return () => subscription.unsubscribe();
}
