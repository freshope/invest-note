// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from "vitest";

// platform 분기 제어: 웹=localStorage, 네이티브=secure storage.
const mockIsNative = vi.fn(() => false);
vi.mock("@/lib/platform", () => ({
  isNativePlatform: () => mockIsNative(),
}));

// 네이티브 secure storage 모킹(in-memory Map 백킹).
const secure = {
  store: new Map<string, string>(),
  setItem: vi.fn(async (k: string, v: string) => {
    secure.store.set(k, v);
  }),
  getItem: vi.fn(async (k: string) => secure.store.get(k) ?? null),
  remove: vi.fn(async (k: string) => {
    secure.store.delete(k);
  }),
};
vi.mock("@aparajita/capacitor-secure-storage", () => ({
  SecureStorage: {
    setItem: (k: string, v: string) => secure.setItem(k, v),
    getItem: (k: string) => secure.getItem(k),
    remove: (k: string) => secure.remove(k),
  },
}));

import * as store from "../token-store";

const ACCESS = "auth.access_token";
const REFRESH = "auth.refresh_token";
const VERIFIER = "auth.pkce_verifier";

describe("token-store — 웹 localStorage 분기", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsNative.mockReturnValue(false);
    localStorage.clear();
  });

  it("saveTokens → localStorage, getAccessTokenRaw/getRefreshToken 회수", async () => {
    await store.saveTokens({ access: "a", refresh: "r" });
    expect(localStorage.getItem(ACCESS)).toBe("a");
    expect(localStorage.getItem(REFRESH)).toBe("r");
    expect(await store.getAccessTokenRaw()).toBe("a");
    expect(await store.getRefreshToken()).toBe("r");
    expect(secure.setItem).not.toHaveBeenCalled(); // secure storage 미사용
  });

  it("clearTokens → localStorage 제거", async () => {
    await store.saveTokens({ access: "a", refresh: "r" });
    await store.clearTokens();
    expect(await store.getAccessTokenRaw()).toBeNull();
    expect(await store.getRefreshToken()).toBeNull();
  });

  it("verifier 저장/조회/삭제 → localStorage", async () => {
    await store.saveVerifier("v");
    expect(localStorage.getItem(VERIFIER)).toBe("v");
    expect(await store.getVerifier()).toBe("v");
    await store.clearVerifier();
    expect(await store.getVerifier()).toBeNull();
  });

  it("localStorage 접근 throw(private mode 등) → read 는 null graceful", async () => {
    const spy = vi
      .spyOn(Storage.prototype, "getItem")
      .mockImplementation(() => {
        throw new Error("private mode");
      });
    expect(await store.getAccessTokenRaw()).toBeNull();
    expect(await store.getVerifier()).toBeNull();
    spy.mockRestore();
  });
});

describe("token-store — 네이티브 secure storage 분기(C5 불변)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsNative.mockReturnValue(true);
    secure.store.clear();
  });

  it("saveTokens → secure storage, getAccessTokenRaw 회수", async () => {
    await store.saveTokens({ access: "a", refresh: "r" });
    expect(secure.setItem).toHaveBeenCalledWith(ACCESS, "a");
    expect(secure.setItem).toHaveBeenCalledWith(REFRESH, "r");
    expect(await store.getAccessTokenRaw()).toBe("a");
  });

  it("clearTokens → secure storage remove", async () => {
    await store.saveTokens({ access: "a", refresh: "r" });
    await store.clearTokens();
    expect(secure.remove).toHaveBeenCalledWith(ACCESS);
    expect(await store.getAccessTokenRaw()).toBeNull();
  });

  it("verifier secure storage 경유(C2)", async () => {
    await store.saveVerifier("v");
    expect(secure.setItem).toHaveBeenCalledWith(VERIFIER, "v");
    expect(await store.getVerifier()).toBe("v");
  });
});
