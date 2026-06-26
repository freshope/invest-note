// 어드민 web 토큰 store — localStorage 백킹(app 의 native secure-storage 대체).
// 기존 auth SDK(pkce flowType)도 localStorage 였으므로 회귀 없음. 내부 allowlist 콘솔.
//
// sync localStorage 를 async 함수로 감싸 app token-store 와 동형 시그니처를 유지한다
// (index.ts 미러링 용이 — await 호출부 동일). 키는 app 과 동일 네이밍.
//
// ⚠️ verifier 는 full-page 리다이렉트 왕복을 생존해야 하므로 메모리 불가 → localStorage.
// 교환 성공 후 clearVerifier 로 삭제.

// ACCESS_KEY 는 index.ts 의 크로스탭 'storage' 동기화에서도 참조한다(다른 탭 로그아웃 감지).
export const ACCESS_KEY = "auth.access_token";
const REFRESH_KEY = "auth.refresh_token";
const VERIFIER_KEY = "auth.pkce_verifier";

// localStorage 접근이 throw 하는 환경(Safari private mode·storage 비활성·sandbox)에서 read 는
// 로그아웃 상태(null)로 graceful 폴백한다(throw 전파 시 getBearerHeader 가 비-ApiError 로 깨짐).
function safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export async function saveTokens(tokens: {
  access: string;
  refresh: string;
}): Promise<void> {
  localStorage.setItem(ACCESS_KEY, tokens.access);
  localStorage.setItem(REFRESH_KEY, tokens.refresh);
}

export async function getAccessTokenRaw(): Promise<string | null> {
  return safeGet(ACCESS_KEY);
}

export async function getRefreshToken(): Promise<string | null> {
  return safeGet(REFRESH_KEY);
}

export async function clearTokens(): Promise<void> {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export async function saveVerifier(verifier: string): Promise<void> {
  localStorage.setItem(VERIFIER_KEY, verifier);
}

export async function getVerifier(): Promise<string | null> {
  return safeGet(VERIFIER_KEY);
}

export async function clearVerifier(): Promise<void> {
  localStorage.removeItem(VERIFIER_KEY);
}
