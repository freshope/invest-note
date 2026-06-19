// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  buildLoginUrl,
  exchangeToken,
  refreshToken,
  decodeClaims,
  isExpiringSoon,
} from "../be-client";

// base64url(no padding) JWT payload 빌더 — 한글 등 UTF-8 안전(C10 테스트용).
function makeJwt(payload: Record<string, unknown>): string {
  const enc = (obj: Record<string, unknown>) => {
    const json = JSON.stringify(obj);
    const bytes = new TextEncoder().encode(json);
    let binary = "";
    for (const b of bytes) binary += String.fromCharCode(b);
    return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  };
  return `${enc({ alg: "ES256" })}.${enc(payload)}.sig`;
}

describe("be-client", () => {
  describe("buildLoginUrl", () => {
    it("provider·code_challenge·S256 method 를 query 에 포함(C1)", () => {
      const url = buildLoginUrl("google", "chal-abc");
      // 테스트 env 엔 NEXT_PUBLIC_API_BASE_URL 부재 → base 상대 경로. base 주입해 파싱.
      const parsed = new URL(url, "http://test.local");
      expect(parsed.pathname).toBe("/auth/login");
      expect(parsed.searchParams.get("provider")).toBe("google");
      expect(parsed.searchParams.get("code_challenge")).toBe("chal-abc");
      expect(parsed.searchParams.get("code_challenge_method")).toBe("S256");
    });
  });

  describe("decodeClaims (C10)", () => {
    it("sub→id, email 추출", () => {
      const token = makeJwt({ sub: "user-uuid", email: "a@b.com" });
      expect(decodeClaims(token)).toEqual({ id: "user-uuid", email: "a@b.com" });
    });

    it("한글 포함 email round-trip(UTF-8 안전)", () => {
      const token = makeJwt({ sub: "u1", email: "홍길동@example.com" });
      expect(decodeClaims(token)).toEqual({
        id: "u1",
        email: "홍길동@example.com",
      });
    });

    it("email 없으면 null email", () => {
      const token = makeJwt({ sub: "u1" });
      expect(decodeClaims(token)).toEqual({ id: "u1", email: null });
    });

    it("sub 없으면 전체 null", () => {
      expect(decodeClaims(makeJwt({ email: "a@b.com" }))).toBeNull();
    });

    it("형식 깨진 토큰 → null", () => {
      expect(decodeClaims("not-a-jwt")).toBeNull();
    });
  });

  describe("isExpiringSoon (C3/C9)", () => {
    it("skew 내 만료 임박이면 true", () => {
      const exp = Math.floor(Date.now() / 1000) + 30; // 30s 후 만료
      expect(isExpiringSoon(makeJwt({ exp }), 60)).toBe(true);
    });

    it("skew 밖 충분히 남으면 false", () => {
      const exp = Math.floor(Date.now() / 1000) + 600; // 10분 후
      expect(isExpiringSoon(makeJwt({ exp }), 60)).toBe(false);
    });

    it("exp 없으면 만료로 간주(true)", () => {
      expect(isExpiringSoon(makeJwt({ sub: "u1" }), 60)).toBe(true);
    });
  });

  describe("exchangeToken / refreshToken (fetch)", () => {
    const fetchMock = vi.fn();
    beforeEach(() => {
      vi.stubGlobal("fetch", fetchMock);
      fetchMock.mockReset();
    });
    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it("exchangeToken: {code, code_verifier} POST → {access, refresh}", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({
          access_token: "acc",
          refresh_token: "ref",
          token_type: "Bearer",
        }),
      });
      const tokens = await exchangeToken("code-1", "verifier-1");
      expect(tokens).toEqual({ access: "acc", refresh: "ref" });
      const [, init] = fetchMock.mock.calls[0];
      expect(JSON.parse(init.body)).toEqual({
        code: "code-1",
        code_verifier: "verifier-1",
      });
    });

    it("refreshToken: {refresh_token} POST → {access, refresh}", async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({
          access_token: "acc2",
          refresh_token: "ref2",
          token_type: "Bearer",
        }),
      });
      const tokens = await refreshToken("old-ref");
      expect(tokens).toEqual({ access: "acc2", refresh: "ref2" });
      const [, init] = fetchMock.mock.calls[0];
      expect(JSON.parse(init.body)).toEqual({ refresh_token: "old-ref" });
    });

    it("비-2xx(503 dormant) → throw(C7)", async () => {
      fetchMock.mockResolvedValue({ ok: false, status: 503 });
      await expect(exchangeToken("c", "v")).rejects.toThrow();
    });

    it("401(PKCE 불일치) → throw", async () => {
      fetchMock.mockResolvedValue({ ok: false, status: 401 });
      await expect(refreshToken("r")).rejects.toThrow();
    });
  });
});
