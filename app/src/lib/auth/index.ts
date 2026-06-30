// Provider-neutral auth 인터페이스. 외부(컴포넌트·lib/api·페이지)는 이 모듈만 사용한다.
// 인증은 웹·네이티브 모두 BE OAuth flow(BE store/token) 단일 경로다. platform 분기는
// 로그인 시작 방식(네이티브=인앱브라우저+딥링크, 웹=full-page redirect+https 콜백)과
// 토큰 영속(token-store 내부)에만 있고, 세션 머시너리는 공통이다.
import type { AuthUser, AuthChangeCallback } from "./types";
import { isNativePlatform } from "@/lib/platform";
import {
  generateVerifier,
  challengeFromVerifier,
  isWebCryptoAvailable,
} from "./pkce";
import {
  buildLoginUrl,
  exchangeToken,
  refreshToken,
  revokeSession,
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

type OAuthProvider = "google" | "kakao" | "apple";

// access token 만료 판정 skew(초). exp - skew 이내면 proactive refresh(C3).
const REFRESH_SKEW_SEC = 60;

// ── 자체 listener registry(subscribe 가 토큰 변화 시 emit 으로 통지) ──
const listeners = new Set<AuthChangeCallback>();
function emit(user: AuthUser | null): void {
  for (const cb of listeners) cb(user);
}

// ── 네이티브 세션 상태(G1 클러스터). 아래 4개는 같은 세션을 표현하므로 항상 함께 갱신/무효화 ──
// - refreshPromise: refresh single-flight(C3) in-flight 공유
// - cachedAccess/cachedClaims: hot path(getAccessToken/getUser) storage·디코드 캐시(F#1/F#2), 항상 쌍
// - logoutEpoch: signOut 발생을 monotonic 으로 표식. in-flight doRefresh 가 persist/emit 전에
//   "아직 로그인?"(캡처 epoch == 현재 epoch)을 확인해 로그아웃 후 토큰 부활(C#1) 차단.
let refreshPromise: Promise<string | null> | null = null;
let cachedAccess: string | null = null;
let cachedClaims: AuthUser | null = null;
let logoutEpoch = 0;

// 캐시 채움/비움은 항상 access+claims 쌍으로(desync 방지). saveTokens·cold-start raw 적재 공유.
function setCache(access: string, claims: AuthUser): void {
  cachedAccess = access;
  cachedClaims = claims;
}
function clearCache(): void {
  cachedAccess = null;
  cachedClaims = null;
}

// 새 토큰 저장+통지 단일 seam(E#1). doRefresh·exchangeCodeForSession 공유.
// epoch 가드로 로그아웃 후 부활 차단(C#1), decodeClaims null 이면 저장도 emit 도 안 함(B#2 desync 차단).
// 성공 시 신 access, 중단/실패 시 null 반환(중단 시 user emit 하지 않음 — signOut 이 이미 null emit).
async function persistAndEmit(
  tokens: { access: string; refresh: string },
  epoch: number,
): Promise<string | null> {
  // 네트워크 진행 중 로그아웃 → 저장하지 않음(가장 흔한 창).
  if (epoch !== logoutEpoch) return null;
  const claims = decodeClaims(tokens.access);
  if (!claims) return null;
  await saveTokens(tokens);
  // saveTokens await 사이에 끼어든 로그아웃(torn-write) 재확인 → 부활 잔여 race 차단.
  if (epoch !== logoutEpoch) {
    await clearTokens();
    return null;
  }
  setCache(tokens.access, claims);
  emit(claims);
  return tokens.access;
}

// refresh 실행 본체. 실패(throw/네트워크)는 내부에서 흡수 → clear+logout emit+null(C4).
// throw 를 전파하지 않으므로 동시 awaiter 전원이 null 을 받고, clearTokens 로 raw·캐시가 비워져
// 후속 getAccessToken 은 refresh 재시도 없이 즉시 null(무한루프 차단).
async function doRefresh(): Promise<string | null> {
  // 첫 await 전 epoch 캡처: 이 refresh 가 시작된 시점의 세션. 이후 로그아웃은 epoch 불일치로 감지.
  const epoch = logoutEpoch;
  try {
    const refresh = await getRefreshToken();
    if (!refresh) {
      clearCache();
      await clearTokens();
      emit(null);
      return null;
    }
    const tokens = await refreshToken(refresh);
    return await persistAndEmit(tokens, epoch);
  } catch {
    clearCache();
    await clearTokens();
    emit(null);
    return null;
  }
}

/**
 * OAuth 로그인 시작. 네이티브는 인앱 브라우저용 BE login URL 을 반환하고(login 이 Browser.open),
 * 웹은 `client=web` 으로 full-page redirect(window.location.assign)해 페이지를 이탈한다
 * (어드민 signInWithGoogle 미러링). 웹은 반환 url 이 의미 없어 null 을 돌려준다.
 */
export async function signInWithOAuth(
  provider: OAuthProvider,
): Promise<{ url: string | null }> {
  // G3: WebCrypto(S256) 부재면 silent 사망 대신 명시적 throw → 호출부(login)가 에러 라우팅.
  if (!isWebCryptoAvailable()) {
    throw new Error("WebCrypto unavailable: PKCE S256 not supported");
  }
  // PKCE: verifier 생성 → 영속 store(네이티브 cold-start·웹 redirect 왕복 생존 C2) → S256 challenge.
  const verifier = generateVerifier();
  await saveVerifier(verifier);
  const challenge = await challengeFromVerifier(verifier);
  if (isNativePlatform()) {
    return { url: buildLoginUrl(provider, challenge) };
  }
  window.location.assign(buildLoginUrl(provider, challenge, "web"));
  return { url: null };
}

/** 현재 세션의 access token(Bearer 주입용). 없으면 null. */
export async function getAccessToken(): Promise<string | null> {
  // hot path: 캐시 우선(F#1). 캐시 유효(만료 임박 아님)면 storage·디코드 생략.
  if (cachedAccess && !isExpiringSoon(cachedAccess, REFRESH_SKEW_SEC)) {
    return cachedAccess;
  }
  // 캐시 miss(cold start) → storage 1회 적재 후 캐시 채움.
  if (!cachedAccess) {
    // read 전 epoch 캡처: getAccessTokenRaw await 중 로그아웃이 완주하면(epoch++)
    // pre-clear stale 토큰이 resolve 되더라도 캐시 부활(C#1) 없이 null 반환(persistAndEmit 와 동일 idiom).
    const epoch = logoutEpoch;
    const raw = await getAccessTokenRaw();
    if (epoch !== logoutEpoch) return null;
    if (!raw) return null;
    const claims = decodeClaims(raw);
    if (claims) setCache(raw, claims);
    if (!isExpiringSoon(raw, REFRESH_SKEW_SEC)) return raw;
  }
  // 만료 임박 → single-flight refresh. 동시 호출은 같은 promise 공유(C3).
  if (!refreshPromise) {
    refreshPromise = doRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

/** 현재 로그인 사용자(provider-neutral). 없으면 null. */
export async function getUser(): Promise<AuthUser | null> {
  // refresh-aware 토큰 확보(C9). getAccessToken 이 캐시 claims 도 채우므로 재사용(F#2 이중 디코드 해소).
  const token = await getAccessToken();
  if (!token) return null;
  // 캐시가 같은 토큰을 가리키면 claims 재사용, 아니면(드뭄) 디코드.
  if (cachedAccess === token && cachedClaims) return cachedClaims;
  return decodeClaims(token);
}

/** 로그아웃. store clear + logout emit(서버 미호출, C11). */
export async function signOut(): Promise<void> {
  // 동기 구간에서 먼저 세션 상태 전부 무효화(C#1). epoch 증가는 clearTokens await 전에 일어나
  // in-flight doRefresh 가 persist 직전 epoch 불일치를 보고 토큰을 부활시키지 못하게 한다.
  logoutEpoch++;
  // 서버측 refresh revoke(best-effort) — clearTokens 전에 읽어야 토큰이 남아있다. 네트워크
  // 실패해도 로컬 로그아웃은 무조건 진행(catch 흡수).
  const refresh = await getRefreshToken();
  if (refresh) {
    try {
      await revokeSession(refresh);
    } catch {
      /* 로컬 정리 우선 — revoke 실패 무시 */
    }
  }
  clearCache();
  refreshPromise = null;
  await clearTokens();
  emit(null);
}

/** 인증 상태 변화 구독. 해제 함수를 반환한다. */
export function subscribe(callback: AuthChangeCallback): () => void {
  listeners.add(callback);
  return () => {
    listeners.delete(callback);
  };
}

/**
 * 인가 code 를 세션으로 교환. 실패 시 throw(딥링크 핸들러·웹 콜백 라우팅용).
 * BE /auth/token(code + PKCE verifier)로 교환한다.
 */
export async function exchangeCodeForSession(code: string): Promise<void> {
  const verifier = await getVerifier();
  if (!verifier) throw new Error("missing PKCE verifier");
  const epoch = logoutEpoch;
  // exchangeToken 이 throw(network/transient)하면 아래 clearVerifier 미도달 → verifier 보존
  // (2b-1 BE 는 실패 시 code 미소진 — peek-before-consume → 재교환 가능). finally 금지.
  const tokens = await exchangeToken(code, verifier);
  // 교환 성공 = BE 가 code 소진 → verifier 재사용 불가하므로 persist 결과와 무관하게 정리.
  await clearVerifier();
  // persist 가 no-op(decodeClaims null·로그아웃 interleave) → 토큰 미저장. 이때 success 로
  // resolve 하면 콜백이 "/"로 갔다가 즉시 /login 으로 무증상 튕김 → 명시적 throw 로
  // 콜백이 /login?error 를 보이게 한다(어드민 index.ts 미러링).
  const access = await persistAndEmit(tokens, epoch);
  if (!access) throw new Error("session not established after token exchange");
}

/**
 * 테스트 전용: 모듈 스코프 네이티브 세션 상태 리셋. 캐시/epoch/refreshPromise 가
 * 케이스 간 누수되면 거짓 통과/실패가 나므로 beforeEach 에서 호출한다. 프로덕션 미사용.
 */
export function __resetNativeSessionForTest(): void {
  refreshPromise = null;
  cachedAccess = null;
  cachedClaims = null;
  logoutEpoch = 0;
  listeners.clear();
}
