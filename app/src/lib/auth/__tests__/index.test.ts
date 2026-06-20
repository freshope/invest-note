import { describe, it, expect, vi, beforeEach } from "vitest";

// ── mock 대상: platform·foundation 모듈·supabase-client ──
const mockIsNative = vi.fn(() => true);
vi.mock("@/lib/platform", () => ({
  isNativePlatform: () => mockIsNative(),
}));

vi.mock("../pkce", () => ({
  generateVerifier: vi.fn(() => "verifier-fixed"),
  challengeFromVerifier: vi.fn(async () => "challenge-fixed"),
  isWebCryptoAvailable: vi.fn(() => true),
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
// getAccessTokenRaw 를 OS getItem 처럼 "호출 시점 값을 스냅샷"하는 read seam 으로 둔다.
// 기본은 즉시 resolve(tokenStore.access). cold-start race 테스트는 이 핸들을 deferred 로 덮어
// read in-flight 중 signOut 을 끼워넣는다.
const storeMock = {
  getAccessTokenRaw: vi.fn(async () => tokenStore.access),
};
vi.mock("../token-store", () => ({
  saveTokens: vi.fn(async (t: { access: string; refresh: string }) => {
    tokenStore.access = t.access;
    tokenStore.refresh = t.refresh;
  }),
  getAccessTokenRaw: () => storeMock.getAccessTokenRaw(),
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
// 실제 app-config 모듈의 sync 캐시 setter(seam). mock 하지 않고 setter 로만 플래그를 제어해
// "필드 부재→OFF"·"fetch 실패→OFF" 가 검증하는 실제 ?? false 경로를 보존한다.
import { setBeAuthEnabled } from "@/lib/api/app-config";

function resetStore() {
  tokenStore.access = null;
  tokenStore.refresh = null;
  tokenStore.verifier = null;
}

describe("lib/auth index — 네이티브 BE flow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetStore();
    // 모듈 스코프 캐시/epoch/listeners 누수 차단(G1).
    auth.__resetNativeSessionForTest();
    mockIsNative.mockReturnValue(true);
    // 2b-4: BE flow 는 네이티브 + 플래그 ON. 이 describe 는 BE flow 분기를 검증하므로 ON 고정.
    setBeAuthEnabled(true);
    beClient.isExpiringSoon.mockReturnValue(false);
    // clearAllMocks 가 구현을 지우므로 기본 read 동작 복원.
    storeMock.getAccessTokenRaw.mockImplementation(async () => tokenStore.access);
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

  it("exchangeCodeForSession: transient 실패 시 verifier 보존(G2 — 재교환 가능)", async () => {
    tokenStore.verifier = "verifier-fixed";
    beClient.exchangeToken.mockRejectedValue(new Error("503 dormant"));

    await expect(auth.exchangeCodeForSession("code-1")).rejects.toThrow();
    // 성공 시에만 clearVerifier → 실패 시 보존(BE 는 code 미소진, 재교환용).
    expect(tokenStore.verifier).toBe("verifier-fixed");
    expect(tokenStore.access).toBeNull();
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

  it("single-flight: 동시 N회 만료 호출 → refresh fetch 1회, 전원 같은 신 토큰 + positive emit(C3/G7)", async () => {
    tokenStore.access = "expired";
    tokenStore.refresh = "ref-old";
    beClient.isExpiringSoon.mockReturnValue(true);
    let resolveRefresh!: (v: { access: string; refresh: string }) => void;
    beClient.refreshToken.mockReturnValue(
      new Promise((r) => {
        resolveRefresh = r;
      }),
    );
    const received: unknown[] = [];
    auth.subscribe((u) => received.push(u));

    const calls = [auth.getAccessToken(), auth.getAccessToken(), auth.getAccessToken()];
    resolveRefresh({ access: "new-acc", refresh: "new-ref" });
    const results = await Promise.all(calls);

    expect(beClient.refreshToken).toHaveBeenCalledTimes(1);
    expect(results).toEqual(["new-acc", "new-acc", "new-acc"]);
    expect(tokenStore.access).toBe("new-acc");
    // refresh 성공 → 디코드된 user 를 1회 emit(positive 경로 회귀 가드 B#3).
    expect(received).toEqual([{ id: "id-new-acc", email: "new-acc@x.com" }]);
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

  it("logout-during-refresh: refresh in-flight 중 signOut → 로그아웃 유지, 토큰 부활 없음(G1/C#1)", async () => {
    tokenStore.access = "expired";
    tokenStore.refresh = "ref-old";
    beClient.isExpiringSoon.mockReturnValue(true);
    let resolveRefresh!: (v: { access: string; refresh: string }) => void;
    beClient.refreshToken.mockReturnValue(
      new Promise((r) => {
        resolveRefresh = r;
      }),
    );
    const received: unknown[] = [];
    auth.subscribe((u) => received.push(u));

    // refresh 네트워크 in-flight 시작. getRefreshToken(non-null) 통과 후 refreshToken 호출까지
    // 대기해야 실제 race 경로(b: 네트워크 in-flight 중 logout)에 닿는다(epoch 가드가 도는 경로).
    const tokenPromise = auth.getAccessToken();
    await vi.waitFor(() => expect(beClient.refreshToken).toHaveBeenCalled());
    // 네트워크 응답 도착 전에 로그아웃(epoch 0→1 + clearTokens + emit null)
    await auth.signOut();
    // 그 다음 refresh 가 신 토큰으로 resolve — persistAndEmit(epoch=0) 이 logoutEpoch(1) 과
    // 불일치를 보고 저장/emit 금지(부활 차단).
    resolveRefresh({ access: "resurrected-acc", refresh: "resurrected-ref" });

    expect(await tokenPromise).toBeNull();
    // secure storage(mock) 양쪽 비움 — 토큰 부활 없음
    expect(tokenStore.access).toBeNull();
    expect(tokenStore.refresh).toBeNull();
    // 마지막 emit 은 logout(null), resurrected user emit 없음
    expect(received[received.length - 1]).toBeNull();
    expect(received).not.toContainEqual({
      id: "id-resurrected-acc",
      email: "resurrected-acc@x.com",
    });
    // 후속 getAccessToken: 캐시·storage 모두 비어 즉시 null(부활 재시도 없음)
    beClient.refreshToken.mockClear();
    expect(await auth.getAccessToken()).toBeNull();
  });

  it("logout-during-cold-start: storage read in-flight 중 signOut → stale 토큰 부활 없음(G1 cold-start seam)", async () => {
    // cold start(캐시 비어있음). storage 에는 아직 유효한 토큰이 있다.
    tokenStore.access = "stale-acc";
    beClient.isExpiringSoon.mockReturnValue(false);
    // getAccessTokenRaw 를 deferred 로: 호출 시점에 "stale-acc"를 스냅샷하지만 resolve 는 지연.
    // signOut 이 read await 도중 완주(epoch++, clearTokens)한 뒤에 stale 값을 resolve 한다.
    let resolveRead!: (v: string | null) => void;
    const snapshot = tokenStore.access;
    storeMock.getAccessTokenRaw.mockImplementation(
      () =>
        new Promise<string | null>((r) => {
          resolveRead = () => r(snapshot);
        }),
    );

    const tokenPromise = auth.getAccessToken();
    await vi.waitFor(() => expect(storeMock.getAccessTokenRaw).toHaveBeenCalled());
    // read in-flight 중 로그아웃(epoch 0→1, clearTokens, emit null) — 동기 구간에서 epoch 즉시 증가.
    await auth.signOut();
    // pre-clear stale 토큰이 뒤늦게 resolve — cold-start epoch 가드가 불일치를 보고 null 반환.
    resolveRead("stale-acc");

    expect(await tokenPromise).toBeNull();
    // 캐시 부활 없음: storage 도 비었으니(signOut 의 clearTokens) 후속 read 는 default 동작으로 복원해
    // null 을 반환 → getUser 도 null. (deferred 를 유지하면 두 번째 read 가 새 미해결 promise 로 멈춤)
    storeMock.getAccessTokenRaw.mockImplementation(async () => tokenStore.access);
    expect(await auth.getUser()).toBeNull();
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
    // 플래그 캐시는 auth 모듈 밖(app-config 싱글톤)이라 케이스 간 누수됨 → 명시 리셋.
    // 웹은 isNativePlatform=false 라 값과 무관히 Supabase 지만 누수 차단 위해 OFF 고정.
    setBeAuthEnabled(false);
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

// 2b-4 fail-safe 본체: 네이티브이지만 플래그 OFF(미수신/fetch 실패/필드 부재 포함) →
// BE flow 미진입, Supabase flow 로 폴백(현재 라이브 무회귀). isBeAuthFlow seam 의 핵심 보증.
describe("lib/auth index — 네이티브 + 플래그 OFF fail-safe(2b-4)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetStore();
    auth.__resetNativeSessionForTest();
    mockIsNative.mockReturnValue(true); // 네이티브 환경
    setBeAuthEnabled(false); // 플래그 OFF(default = fetch 미완/실패/필드 부재와 동치)
  });

  it("signInWithOAuth: BE 미진입 → supabase 호출, verifier 미저장", async () => {
    const { url } = await auth.signInWithOAuth("google", {
      redirectTo: "r",
      skipBrowserRedirect: true,
    });
    expect(supabaseAuth.signInWithOAuth).toHaveBeenCalled();
    expect(url).toBe("https://supabase/oauth");
    expect(tokenStore.verifier).toBeNull();
    expect(beClient.buildLoginUrl).not.toHaveBeenCalled();
  });

  it("getAccessToken: supabase getSession 폴백", async () => {
    expect(await auth.getAccessToken()).toBe("sb-access");
  });

  it("getUser: supabase session.user 폴백", async () => {
    expect(await auth.getUser()).toEqual({ id: "sb-id", email: "sb@x.com" });
  });

  it("signOut: supabase signOut({scope:local}) 폴백", async () => {
    await auth.signOut();
    expect(supabaseAuth.signOut).toHaveBeenCalledWith({ scope: "local" });
  });

  it("exchangeCodeForSession: supabase 교환 폴백, BE 미호출", async () => {
    await auth.exchangeCodeForSession("code");
    expect(supabaseAuth.exchangeCodeForSession).toHaveBeenCalledWith("code");
    expect(beClient.exchangeToken).not.toHaveBeenCalled();
  });

  it("subscribe: supabase onAuthStateChange 폴백", () => {
    auth.subscribe(() => {});
    expect(supabaseAuth.onAuthStateChange).toHaveBeenCalled();
  });
});
