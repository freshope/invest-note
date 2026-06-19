// Provider-neutral auth 인터페이스. 외부(컴포넌트·lib/api·페이지)는 이 모듈만 사용한다.
// 네이티브는 BE OAuth flow(BE store/token), 웹은 expand 동안 Supabase 유지(C8 이중화).
// @supabase/supabase-js 의 결합은 supabase-client.ts 뒤에 격리되어 있다(웹 전용).
import { getSupabaseClient } from "./supabase-client";
import type { AuthUser, AuthChangeCallback } from "./types";
import { isNativePlatform } from "@/lib/platform";
import { generateVerifier, challengeFromVerifier } from "./pkce";
import {
  buildLoginUrl,
  exchangeToken,
  refreshToken,
  decodeClaims,
  isExpiringSoon,
} from "./be-client";
import {
  saveTokens,
  getAccessTokenRaw,
  getRefreshToken,
  clearTokens,
  saveVerifier,
  getVerifier,
  clearVerifier,
} from "./token-store";

export type { AuthUser, AuthChangeCallback } from "./types";

function toAuthUser(
  user: { id: string; email?: string } | null | undefined,
): AuthUser | null {
  if (!user) return null;
  return { id: user.id, email: user.email ?? null };
}

type OAuthProvider = "google" | "kakao" | "apple";

// access token 만료 판정 skew(초). exp - skew 이내면 proactive refresh(C3).
const REFRESH_SKEW_SEC = 60;

// ── 네이티브: 자체 listener registry(subscribe 대체, supabase-js onAuthStateChange 상실 대체) ──
const listeners = new Set<AuthChangeCallback>();
function emit(user: AuthUser | null): void {
  for (const cb of listeners) cb(user);
}

// ── 네이티브: refresh single-flight(C3). 모듈 스코프 in-flight promise 공유 ──
let refreshPromise: Promise<string | null> | null = null;

// refresh 실행 본체. 실패(throw/네트워크)는 내부에서 흡수 → clear+logout emit+null(C4).
// throw 를 전파하지 않으므로 동시 awaiter 전원이 null 을 받고, clearTokens 로 raw 가 비워져
// 후속 getAccessToken 은 refresh 재시도 없이 즉시 null(무한루프 차단).
async function doRefresh(): Promise<string | null> {
  try {
    const refresh = await getRefreshToken();
    if (!refresh) {
      await clearTokens();
      emit(null);
      return null;
    }
    const tokens = await refreshToken(refresh);
    await saveTokens(tokens);
    emit(decodeClaims(tokens.access));
    return tokens.access;
  } catch {
    await clearTokens();
    emit(null);
    return null;
  }
}

/**
 * OAuth 로그인 시작. 네이티브는 BE flow URL(인앱 브라우저용)을 반환한다.
 * 웹은 supabase-js 가 skipBrowserRedirect 로 받은 url 을 반환.
 */
export async function signInWithOAuth(
  provider: OAuthProvider,
  options: { redirectTo: string; skipBrowserRedirect: boolean },
): Promise<{ url: string | null }> {
  if (isNativePlatform()) {
    // PKCE: verifier 생성 → secure storage 영속(cold-start 생존 C2) → S256 challenge.
    const verifier = generateVerifier();
    await saveVerifier(verifier);
    const challenge = await challengeFromVerifier(verifier);
    return { url: buildLoginUrl(provider, challenge) };
  }
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
  if (isNativePlatform()) {
    const raw = await getAccessTokenRaw();
    if (!raw) return null;
    if (!isExpiringSoon(raw, REFRESH_SKEW_SEC)) return raw;
    // 만료 임박 → single-flight refresh. 동시 호출은 같은 promise 공유(C3).
    if (!refreshPromise) {
      refreshPromise = doRefresh().finally(() => {
        refreshPromise = null;
      });
    }
    return refreshPromise;
  }
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
  if (isNativePlatform()) {
    // refresh-aware 토큰 확보 후 디코드(C9). 토큰 없으면 null.
    const token = await getAccessToken();
    if (!token) return null;
    return decodeClaims(token);
  }
  try {
    const {
      data: { session },
    } = await getSupabaseClient().auth.getSession();
    return toAuthUser(session?.user);
  } catch {
    return null;
  }
}

/** 로그아웃. 네이티브는 store clear + logout emit(서버 미호출, C11). */
export async function signOut(): Promise<void> {
  if (isNativePlatform()) {
    await clearTokens();
    emit(null);
    return;
  }
  // 서버 호출 실패에도 로컬 세션은 무조건 비우도록 scope: "local" 고정.
  await getSupabaseClient().auth.signOut({ scope: "local" });
}

/** 인증 상태 변화 구독. 해제 함수를 반환한다. */
export function subscribe(callback: AuthChangeCallback): () => void {
  if (isNativePlatform()) {
    listeners.add(callback);
    return () => {
      listeners.delete(callback);
    };
  }
  const {
    data: { subscription },
  } = getSupabaseClient().auth.onAuthStateChange((_event, session) => {
    callback(toAuthUser(session?.user));
  });
  return () => subscription.unsubscribe();
}

/**
 * 인가 code 를 세션으로 교환. 실패 시 throw(딥링크 핸들러 라우팅용).
 * 네이티브는 BE /auth/token(code + PKCE verifier), 웹은 supabase PKCE.
 */
export async function exchangeCodeForSession(code: string): Promise<void> {
  if (isNativePlatform()) {
    const verifier = await getVerifier();
    if (!verifier) throw new Error("missing PKCE verifier");
    try {
      const tokens = await exchangeToken(code, verifier);
      await saveTokens(tokens);
      emit(decodeClaims(tokens.access));
    } finally {
      // 성공/실패 무관 verifier 삭제(C2 — 일회용).
      await clearVerifier();
    }
    return;
  }
  const { error } = await getSupabaseClient().auth.exchangeCodeForSession(code);
  if (error) throw error;
}
