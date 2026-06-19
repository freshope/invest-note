import { describe, it, expect, vi, beforeEach } from "vitest";

// secure storage 플러그인 mock — 인메모리 맵으로 native Keychain/Keystore 대체.
const store = new Map<string, string>();
vi.mock("@aparajita/capacitor-secure-storage", () => ({
  SecureStorage: {
    setItem: vi.fn(async (key: string, value: string) => {
      store.set(key, value);
    }),
    getItem: vi.fn(async (key: string) => store.get(key) ?? null),
    remove: vi.fn(async (key: string) => {
      const had = store.has(key);
      store.delete(key);
      return had;
    }),
  },
}));

import {
  saveTokens,
  getAccessTokenRaw,
  getRefreshToken,
  clearTokens,
  saveVerifier,
  getVerifier,
  clearVerifier,
} from "../token-store";
import { SecureStorage } from "@aparajita/capacitor-secure-storage";

describe("token-store", () => {
  beforeEach(() => {
    store.clear();
    vi.clearAllMocks();
  });

  it("saveTokens → getAccessTokenRaw / getRefreshToken round-trip", async () => {
    await saveTokens({ access: "acc-1", refresh: "ref-1" });
    expect(await getAccessTokenRaw()).toBe("acc-1");
    expect(await getRefreshToken()).toBe("ref-1");
  });

  it("clearTokens 후 access/refresh 모두 null", async () => {
    await saveTokens({ access: "acc-1", refresh: "ref-1" });
    await clearTokens();
    expect(await getAccessTokenRaw()).toBeNull();
    expect(await getRefreshToken()).toBeNull();
  });

  it("verifier 는 토큰과 별도 키로 저장·조회·삭제(C2)", async () => {
    await saveTokens({ access: "acc-1", refresh: "ref-1" });
    await saveVerifier("verifier-xyz");
    expect(await getVerifier()).toBe("verifier-xyz");
    // verifier clear 가 토큰을 건드리지 않음
    await clearVerifier();
    expect(await getVerifier()).toBeNull();
    expect(await getAccessTokenRaw()).toBe("acc-1");
  });

  it("모든 쓰기가 secure storage(SecureStorage) 경유 — localStorage 미사용(C5)", async () => {
    await saveTokens({ access: "acc-1", refresh: "ref-1" });
    await saveVerifier("v");
    expect(SecureStorage.setItem).toHaveBeenCalledWith("auth.access_token", "acc-1");
    expect(SecureStorage.setItem).toHaveBeenCalledWith("auth.refresh_token", "ref-1");
    expect(SecureStorage.setItem).toHaveBeenCalledWith("auth.pkce_verifier", "v");
  });
});
