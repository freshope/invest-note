import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  fetchAppConfig,
  getBeAuthEnabled,
  ensureBeAuthFlagLoaded,
  __resetAppConfigForTest,
} from "./app-config";

// fetchAppConfig 의 실제 ?? false / 성공 시 settle 경로를 검증한다(모듈 mock 금지).
// fetch 만 stub 해 wire 응답을 주입하고, sync 캐시는 getBeAuthEnabled 로 관찰한다.
function mockFetch(impl: () => Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(impl));
}
function jsonResponse(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as Response;
}
function config(beAuthEnabled?: boolean) {
  return {
    minSupportedVersion: "",
    storeUrl: { ios: "", android: "" },
    ...(beAuthEnabled === undefined ? {} : { beAuthEnabled }),
  };
}

describe("lib/api/app-config — beAuthEnabled 캐시(2b-4)", () => {
  beforeEach(() => {
    __resetAppConfigForTest(); // 싱글톤(settled/configPromise/캐시) 누수 차단
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("getBeAuthEnabled: 초기값 false(fetch 전)", () => {
    expect(getBeAuthEnabled()).toBe(false);
  });

  it("fetch 성공 + beAuthEnabled:true → 캐시 ON", async () => {
    mockFetch(async () => jsonResponse(config(true)));
    await fetchAppConfig();
    expect(getBeAuthEnabled()).toBe(true);
  });

  it("fetch 성공 + beAuthEnabled:false → 캐시 OFF", async () => {
    mockFetch(async () => jsonResponse(config(false)));
    await fetchAppConfig();
    expect(getBeAuthEnabled()).toBe(false);
  });

  it("필드 부재(구 BE) → ?? false 로 OFF", async () => {
    mockFetch(async () => jsonResponse(config()));
    await fetchAppConfig();
    expect(getBeAuthEnabled()).toBe(false);
  });

  it("fetch 실패(!ok) → throw, 캐시 OFF 유지", async () => {
    mockFetch(async () => ({ ok: false, status: 503 }) as Response);
    await expect(fetchAppConfig()).rejects.toThrow();
    expect(getBeAuthEnabled()).toBe(false);
  });

  it("fetch reject(네트워크) → 캐시 OFF 유지", async () => {
    mockFetch(async () => {
      throw new Error("network");
    });
    await expect(fetchAppConfig()).rejects.toThrow();
    expect(getBeAuthEnabled()).toBe(false);
  });

  it("memoize: fetchAppConfig 재호출은 단일 fetch 공유", async () => {
    const fn = vi.fn(async () => jsonResponse(config(true)));
    vi.stubGlobal("fetch", fn);
    await Promise.all([fetchAppConfig(), fetchAppConfig()]);
    await fetchAppConfig();
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("세션 고정: 첫 settle(ON) 후 ensureBeAuthFlagLoaded 가 값을 못 바꾼다", async () => {
    mockFetch(async () => jsonResponse(config(true)));
    await fetchAppConfig(); // settle(true)
    await ensureBeAuthFlagLoaded(0); // 이미 settled → 즉시 반환, no-op
    expect(getBeAuthEnabled()).toBe(true);
  });

  it("ensureBeAuthFlagLoaded: timeout(미settle) → OFF 로 세션 고정", async () => {
    // fetch 가 영원히 안 끝남(오프라인 시뮬) → timeout 0 으로 즉시 OFF settle.
    mockFetch(() => new Promise<Response>(() => {}));
    await ensureBeAuthFlagLoaded(0);
    expect(getBeAuthEnabled()).toBe(false);
    // timeout 으로 settled 됐으므로, 이후 fetch 가 늦게 ON 을 줘도 무시(세션 일관).
    // (같은 configPromise 가 pending 이라 재settle 시도 자체가 없지만 가드도 확인)
    expect(getBeAuthEnabled()).toBe(false);
  });

  it("ensureBeAuthFlagLoaded: fetch 성공 시 그 값으로 settle", async () => {
    mockFetch(async () => jsonResponse(config(true)));
    await ensureBeAuthFlagLoaded(3000);
    expect(getBeAuthEnabled()).toBe(true);
  });
});
