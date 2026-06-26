// BE OAuth flow fetch + access JWT 로컬 디코드. app/src/lib/auth/be-client.ts 미러링.
// 경로는 bare(/v1 아래 아님) — api.ts 와 동일 NEXT_PUBLIC_API_BASE_URL 공유.
//
// 토큰 검증은 안 한다: BE 가 서명 검증, 어드민은 claim 읽기만.

// api.ts 와 동일 env. trailing slash 제거.
const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

export interface BeTokens {
  access: string;
  refresh: string;
}

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

/**
 * 어드민 web 용 BE 로그인 URL. 어드민은 web client 이므로 `client=admin` 을 포함한다
 * (계약 핀) → BE 가 IdP 중개 후 `be_admin_redirect_url` 로 일회용 code 를 돌려준다.
 */
export function buildLoginUrl(provider: string, codeChallenge: string): string {
  const params = new URLSearchParams({
    provider,
    code_challenge: codeChallenge,
    code_challenge_method: "S256",
    client: "admin",
  });
  return `${API_BASE}/auth/login?${params.toString()}`;
}

async function postTokens(path: string, body: unknown): Promise<BeTokens> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  // 비-2xx(만료·PKCE 불일치 401 등) → throw(호출부 라우팅).
  if (!res.ok) {
    throw new Error(`auth request failed (${res.status})`);
  }
  const data = (await res.json()) as TokenResponse;
  return { access: data.access_token, refresh: data.refresh_token };
}

/** 일회용 code + PKCE verifier → BE access/refresh 토큰 교환. */
export function exchangeToken(code: string, verifier: string): Promise<BeTokens> {
  return postTokens("/auth/token", { code, code_verifier: verifier });
}

/** refresh 토큰 회전 — 신 access/refresh 반환. */
export function refreshToken(refresh: string): Promise<BeTokens> {
  return postTokens("/auth/refresh", { refresh_token: refresh });
}

/**
 * 서버측 refresh 무효화(로그아웃). best-effort — BE 는 멱등 200 이고, 네트워크 실패해도
 * 호출부(signOut)가 로컬 정리를 이어가야 하므로 결과를 확인하지 않는다.
 */
export async function revokeSession(refresh: string): Promise<void> {
  await fetch(`${API_BASE}/auth/logout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
}

// ── access JWT 로컬 디코드 (검증 안 함) ──────────────────────────────────────

interface JwtClaims {
  sub?: string;
  email?: string | null;
  exp?: number;
}

// base64url → JSON. 한글 email 안전을 위해 TextDecoder 경유.
function decodePayload(token: string): JwtClaims | null {
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    const b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
    const binary = atob(padded);
    const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
    const json = new TextDecoder().decode(bytes);
    return JSON.parse(json) as JwtClaims;
  } catch {
    return null;
  }
}

/** access token 의 sub/email 추출. 디코드 실패 시 null. */
export function decodeClaims(
  accessToken: string,
): { id: string; email: string | null } | null {
  const claims = decodePayload(accessToken);
  if (!claims?.sub) return null;
  return { id: claims.sub, email: claims.email ?? null };
}

/**
 * access token 이 skewSec 내 만료 임박/만료인지. exp 없으면 만료로 간주.
 */
export function isExpiringSoon(accessToken: string, skewSec: number): boolean {
  const claims = decodePayload(accessToken);
  if (!claims?.exp) return true;
  const nowSec = Date.now() / 1000;
  return claims.exp - skewSec <= nowSec;
}
