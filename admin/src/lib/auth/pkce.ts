// PKCE S256. 어드민 web 이 code_verifier 생성 → code_challenge = base64url(SHA256(verifier)).
// BE 는 enforce-always(S256 외 거부, plain 폴백 없음)이므로 누락/오류 시 전 로그인 거부.
//
// web 은 https secure context 라 WebCrypto 가 항상 존재하지만, silent 실패 대신 명시적
// throw 로 전환하기 위해 isWebCryptoAvailable 가드를 유지한다(app 미러링).

// RFC 7636: verifier 는 43~128 char, unreserved [A-Za-z0-9-._~].
const VERIFIER_BYTES = 32; // base64url 인코딩 시 43 char (최소값)

function base64UrlEncode(bytes: Uint8Array): string {
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/**
 * WebCrypto SHA-256(subtle.digest) 가용 여부. 부재 시 silent 사망 대신
 * signInWithGoogle 시작 전에 호출해 명시적/라우팅 가능한 실패로 전환한다.
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
