// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import { generateVerifier, challengeFromVerifier } from "../pkce";

describe("pkce", () => {
  it("verifier 는 43~128 char, unreserved [A-Za-z0-9-._~]", () => {
    const v = generateVerifier();
    expect(v.length).toBeGreaterThanOrEqual(43);
    expect(v.length).toBeLessThanOrEqual(128);
    expect(v).toMatch(/^[A-Za-z0-9\-._~]+$/);
  });

  it("verifier 는 매번 다름(고엔트로피)", () => {
    expect(generateVerifier()).not.toBe(generateVerifier());
  });

  it("challenge = base64url(SHA256(verifier)) — RFC 7636 표준 벡터(C1)", async () => {
    // RFC 7636 Appendix B 공식 테스트 벡터
    const verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk";
    const challenge = await challengeFromVerifier(verifier);
    expect(challenge).toBe("E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM");
  });

  it("challenge 는 base64url(padding 제거) 형식", async () => {
    const challenge = await challengeFromVerifier(generateVerifier());
    expect(challenge).toMatch(/^[A-Za-z0-9\-_]+$/);
    expect(challenge).not.toContain("=");
  });
});
