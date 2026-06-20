// PKCE S256 (C1). 앱이 code_verifier 생성 → code_challenge = base64url(SHA256(verifier)).
// 2b-1 BE 는 enforce-always(S256 외 거부, plain 폴백 없음)이므로 누락/오류 시 전 로그인 거부.
//
// ⚠️ crypto.subtle.digest 는 jsdom/node 에 항상 있어 unit test 가 부재를 못 잡는다.
// Capacitor WebView(특히 custom scheme origin)에서 부재 시 전 네이티브 로그인 사망 →
// iOS·Android 디바이스 실측 필수(QA carry-forward).

// RFC 7636: verifier 는 43~128 char, unreserved [A-Za-z0-9-._~].
const VERIFIER_BYTES = 32; // base64url 인코딩 시 43 char (최소값)

function base64UrlEncode(bytes: Uint8Array): string {
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/**
 * WebCrypto SHA-256(subtle.digest) 가용 여부(G3). Capacitor WebView 의 non-secure
 * context(custom scheme origin)에서 부재 시 전 네이티브 로그인이 silent 사망하므로,
 * signInWithOAuth 가 시작 전에 호출해 명시적/라우팅 가능한 실패로 전환한다.
 */
export function isWebCryptoAvailable(): boolean {
  return (
    typeof crypto !== "undefined" &&
    typeof crypto.subtle?.digest === "function" &&
    typeof crypto.getRandomValues === "function"
  );
}

/** 고엔트로피 crypto random verifier(43 char base64url, unreserved). */
export function generateVerifier(): string {
  const bytes = new Uint8Array(VERIFIER_BYTES);
  crypto.getRandomValues(bytes);
  return base64UrlEncode(bytes);
}

/** code_challenge = base64url(SHA256(verifier)). WebCrypto subtle.digest 사용. */
export async function challengeFromVerifier(verifier: string): Promise<string> {
  const data = new TextEncoder().encode(verifier);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return base64UrlEncode(new Uint8Array(digest));
}
