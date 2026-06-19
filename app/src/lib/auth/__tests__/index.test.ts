import { describe, it, expect, vi, beforeEach } from "vitest";

// ── mock 대상: platform·foundation 모듈·supabase-client ──
const mockIsNative = vi.fn(() => true);
vi.mock("@/lib/platform", () => ({
  isNativePlatform: () => mockIsNative(),
}));

vi.mock("../pkce", () => ({
  generateVerifier: vi.fn(() => "verifier-fixed"),
  challengeFromVerifier: vi.fn(async () => "challenge-fixed"),
}));

const beClient = {
  buildLoginUrl: vi.fn(
    (p: string, c: string) => `https://be/auth/login?provider=${p}&code_challenge=${c}`,
  ),
  exchangeToken: vi.fn(),
  refreshToken: vi.fn(),
  decodeClaims: vi.fn((t: string) =>
    t ? { id: `id-${t}`, email: `${t}@x.com` } : null,
  ),
  isExpiringSoon: vi.fn((_t: string, _s: number) => false),
};
vi.mock("../be-client", () => ({
  buildLoginUrl: (p: string, c: string) => beClient.buildLoginUrl(p, c),
  exchangeToken: (c: string, v: string) => beClient.exchangeToken(c, v),
  refreshToken: (r: string) => beClient.refreshToken(r),
  decodeClaims: (t: string) => beClient.decodeClaims(t),
  isExpiringSoon: (t: string, s: number) => beClient.isExpiringSoon(t, s),
}));

const tokenStore = {
  access: null as string | null,
  refresh: null as string | null,
  verifier: null as string | null,
};
vi.mock("../token-store", () => ({
  saveTokens: vi.fn(async (t: { access: string; refresh: string }) => {
    tokenStore.access = t.access;
    tokenStore.refresh = t.refresh;
  }),
  getAccessTokenRaw: vi.fn(async () => tokenStore.access),
  getRefreshToken: vi.fn(async () => tokenStore.refresh),
  clearTokens: vi.fn(async () => {
    tokenStore.access = null;
    tokenStore.refresh = null;
  }),
  saveVerifier: vi.fn(async (v: string) => {
    tokenStore.verifier = v;
  }),
  getVerifier: vi.fn(async () => tokenStore.verifier),
  clearVerifier: vi.fn(async () => {
    tokenStore.verifier = null;
  }),
}));

// supabase-client mock(웹 가지 보존 검증용 C8)
const supabaseAuth = {
  signInWithOAuth: vi.fn(async () => ({ data: { url: "https://supabase/oauth" }, error: null })),
  getSession: vi.fn(async () => ({
    data: { session: { access_token: "sb-access", user: { id: "sb-id", email: "sb@x.com" } } },
  })),
  signOut: vi.fn(async () => ({ error: null })),
  onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })),
  setSession: vi.fn(async () => ({ error: null })),
  exchangeCodeForSession: vi.fn(async () => ({ error: null })),
};
vi.mock("../supabase-client", () => ({
  getSupabaseClient: () => ({ auth: supabaseAuth }),
}));

import * as auth from "../index";

function resetStore() {
  tokenStore.access = null;
  tokenStore.refresh = null;
  tokenStore.verifier = null;
}

describe("lib/auth index — 네이티브 BE flow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetStore();
    mockIsNative.mockReturnValue(true);
    beClient.isExpiringSoon.mockReturnValue(false);
  });

  it("signInWithOAuth: verifier 저장 + BE login url(C1/C2)", async () => {
    const { url } = await auth.signInWithOAuth("google", {
      redirectTo: "x",
      skipBrowserRedirect: true,
    });
    expect(tokenStore.verifier).toBe("verifier-fixed");
    expect(url).toContain("code_challenge=challenge-fixed");
    expect(url).toContain("provider=google");
  });

  it("exchangeCodeForSession: token 저장 + verifier 삭제 + emit(C2)", async () => {
    tokenStore.verifier = "verifier-fixed";
    beClient.exchangeToken.mockResolvedValue({ access: "acc", refresh: "ref" });
    const received: unknown[] = [];
    auth.subscribe((u) => received.push(u));

    await auth.exchangeCodeForSession("code-1");
    expect(beClient.exchangeToken).toHaveBeenCalledWith("code-1", "verifier-fixed");
    expect(tokenStore.access).toBe("acc");
    expect(tokenStore.verifier).toBeNull();
    expect(received).toEqual([{ id: "id-acc", email: "acc@x.com" }]);
  });

  it("exchangeCodeForSession: verifier 없으면 throw", async () => {
    tokenStore.verifier = null;
    await expect(auth.exchangeCodeForSession("code")).rejects.toThrow();
  });

  it("getAccessToken: 유효 토큰이면 그대로 반환(refresh 미발생)", async () => {
    tokenStore.access = "valid-acc";
    beClient.isExpiringSoon.mockReturnValue(false);
    expect(await auth.getAccessToken()).toBe("valid-acc");
    expect(beClient.refreshToken).not.toHaveBeenCalled();
  });

  it("getAccessToken: 토큰 없으면 null", async () => {
    tokenStore.access = null;
    expect(await auth.getAccessToken()).toBeNull();
  });

  it("single-flight: 동시 N회 만료 호출 → refresh fetch 1회, 전원 같은 신 토큰(C3)", async () => {
    tokenStore.access = "expired";
    tokenStore.refresh = "ref-old";
    beClient.isExpiringSoon.mockReturnValue(true);
    let resolveRefresh!: (v: { access: string; refresh: string }) => void;
    beClient.refreshToken.mockReturnValue(
      new Promise((r) => {
        resolveRefresh = r;
      }),
    );

    const calls = [auth.getAccessToken(), auth.getAccessToken(), auth.getAccessToken()];
    resolveRefresh({ access: "new-acc", refresh: "new-ref" });
    const results = await Promise.all(calls);

    expect(beClient.refreshToken).toHaveBeenCalledTimes(1);
    expect(results).toEqual(["new-acc", "new-acc", "new-acc"]);
    expect(tokenStore.access).toBe("new-acc");
  });

  it("single-flight 클리어: 첫 refresh 후 다음 만료 주기에 재-refresh 발생(C3 .finally)", async () => {
    tokenStore.access = "expired";
    tokenStore.refresh = "ref-1";
    beClient.isExpiringSoon.mockReturnValue(true);
    beClient.refreshToken
      .mockResolvedValueOnce({ access: "acc-2", refresh: "ref-2" })
      .mockResolvedValueOnce({ access: "acc-3", refresh: "ref-3" });

    expect(await auth.getAccessToken()).toBe("acc-2");
    // 두 번째 주기: 새 access 가 또 만료 임박이라 가정 → 새 refresh promise 생성돼야 함
    expect(await auth.getAccessToken()).toBe("acc-3");
    expect(beClient.refreshToken).toHaveBeenCalledTimes(2);
  });

  it("refresh 실패 → clear + null + logout emit, 후속은 refresh 재시도 안 함(C4)", async () => {
    tokenStore.access = "expired";
    tokenStore.refresh = "ref-bad";
    beClient.isExpiringSoon.mockReturnValue(true);
    beClient.refreshToken.mockRejectedValue(new Error("401"));
    const received: unknown[] = [];
    auth.subscribe((u) => received.push(u));

    expect(await auth.getAccessToken()).toBeNull();
    expect(tokenStore.access).toBeNull();
    expect(received).toEqual([null]);

    // 후속 호출: raw=null 이라 refresh 재시도 없이 즉시 null(무한루프 차단)
    beClient.refreshToken.mockClear();
    expect(await auth.getAccessToken()).toBeNull();
    expect(beClient.refreshToken).not.toHaveBeenCalled();
  });

  it("getUser: refresh-aware 토큰 디코드(C9)", async () => {
    tokenStore.access = "valid";
    beClient.isExpiringSoon.mockReturnValue(false);
    expect(await auth.getUser()).toEqual({ id: "id-valid", email: "valid@x.com" });
  });

  it("getUser: 토큰 없으면 null", async () => {
    tokenStore.access = null;
    expect(await auth.getUser()).toBeNull();
  });

  it("signOut: store clear + emit(null), 서버 미호출(C11)", async () => {
    tokenStore.access = "acc";
    tokenStore.refresh = "ref";
    const received: unknown[] = [];
    auth.subscribe((u) => received.push(u));

    await auth.signOut();
    expect(tokenStore.access).toBeNull();
    expect(received).toEqual([null]);
    expect(supabaseAuth.signOut).not.toHaveBeenCalled();
  });

  it("subscribe 해제 함수가 listener 제거(누수 차단)", async () => {
    const received: unknown[] = [];
    const unsub = auth.subscribe((u) => received.push(u));
    unsub();
    await auth.signOut(); // emit(null) 발화하지만 해제됐으니 미수신
    expect(received).toEqual([]);
  });
});

describe("lib/auth index — 웹 무회귀(C8)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetStore();
    mockIsNative.mockReturnValue(false);
  });

  it("signInWithOAuth: 기존 supabase signInWithOAuth 호출", async () => {
    const { url } = await auth.signInWithOAuth("kakao", {
      redirectTo: "r",
      skipBrowserRedirect: false,
    });
    expect(supabaseAuth.signInWithOAuth).toHaveBeenCalled();
    expect(url).toBe("https://supabase/oauth");
    expect(tokenStore.verifier).toBeNull(); // 네이티브 PKCE 경로 미진입
  });

  it("getAccessToken: 기존 supabase getSession", async () => {
    expect(await auth.getAccessToken()).toBe("sb-access");
  });

  it("getUser: 기존 supabase session.user", async () => {
    expect(await auth.getUser()).toEqual({ id: "sb-id", email: "sb@x.com" });
  });

  it("signOut: 기존 supabase signOut({scope:local})", async () => {
    await auth.signOut();
    expect(supabaseAuth.signOut).toHaveBeenCalledWith({ scope: "local" });
  });

  it("exchangeCodeForSession: 기존 supabase exchangeCodeForSession", async () => {
    await auth.exchangeCodeForSession("code");
    expect(supabaseAuth.exchangeCodeForSession).toHaveBeenCalledWith("code");
    expect(beClient.exchangeToken).not.toHaveBeenCalled();
  });

  it("subscribe: 기존 supabase onAuthStateChange", () => {
    auth.subscribe(() => {});
    expect(supabaseAuth.onAuthStateChange).toHaveBeenCalled();
  });
});
