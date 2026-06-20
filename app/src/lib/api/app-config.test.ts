import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { fetchAppConfig, getBeAuthEnabled, setBeAuthEnabled } from "./app-config";

// fetchAppConfig 의 실제 ?? false / 성공 시 set 경로를 검증한다(모듈 mock 금지).
// fetch 만 stub 해 wire 응답을 주입하고, sync 캐시는 getBeAuthEnabled 로 관찰한다.
function mockFetch(impl: () => Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(impl));
}
function jsonResponse(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as Response;
}

describe("lib/api/app-config — beAuthEnabled 캐시(2b-4)", () => {
  beforeEach(() => {
    setBeAuthEnabled(false); // 캐시 누수 차단(모듈 싱글톤)
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("getBeAuthEnabled: 초기값 false(fetch 전)", () => {
    expect(getBeAuthEnabled()).toBe(false);
  });

  it("fetch 성공 + beAuthEnabled:true → 캐시 ON", async () => {
    mockFetch(async () =>
      jsonResponse({
        minSupportedVersion: "",
        storeUrl: { ios: "", android: "" },
        beAuthEnabled: true,
      }),
    );
    await fetchAppConfig();
    expect(getBeAuthEnabled()).toBe(true);
  });

  it("fetch 성공 + beAuthEnabled:false → 캐시 OFF", async () => {
    mockFetch(async () =>
      jsonResponse({
        minSupportedVersion: "",
        storeUrl: { ios: "", android: "" },
        beAuthEnabled: false,
      }),
    );
    await fetchAppConfig();
    expect(getBeAuthEnabled()).toBe(false);
  });

  it("필드 부재(구 BE) → ?? false 로 OFF", async () => {
    mockFetch(async () =>
      jsonResponse({
        minSupportedVersion: "",
        storeUrl: { ios: "", android: "" },
      }),
    );
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
});
