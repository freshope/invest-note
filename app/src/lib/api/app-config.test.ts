import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { fetchAppConfig, __resetAppConfigForTest } from "./app-config";

// fetch 만 stub 해 wire 응답을 주입하고 force-update 설정(minSupportedVersion/storeUrl)을 검증한다.
function mockFetch(impl: () => Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn(impl));
}
function jsonResponse(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as Response;
}

describe("lib/api/app-config — fetchAppConfig(force-update)", () => {
  beforeEach(() => {
    __resetAppConfigForTest(); // 메모이즈된 configPromise 누수 차단
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("fetch 성공 → minSupportedVersion/storeUrl 반환", async () => {
    mockFetch(async () =>
      jsonResponse({
        minSupportedVersion: "1.3.0",
        storeUrl: { ios: "https://ios", android: "https://android" },
      }),
    );
    const config = await fetchAppConfig();
    expect(config.minSupportedVersion).toBe("1.3.0");
    expect(config.storeUrl).toEqual({ ios: "https://ios", android: "https://android" });
  });

  it("fetch 실패(!ok) → throw", async () => {
    mockFetch(async () => ({ ok: false, status: 503 }) as Response);
    await expect(fetchAppConfig()).rejects.toThrow();
  });

  it("memoize: fetchAppConfig 재호출은 단일 fetch 공유", async () => {
    const fn = vi.fn(async () =>
      jsonResponse({ minSupportedVersion: "1.3.0", storeUrl: { ios: "", android: "" } }),
    );
    vi.stubGlobal("fetch", fn);
    await Promise.all([fetchAppConfig(), fetchAppConfig()]);
    await fetchAppConfig();
    expect(fn).toHaveBeenCalledTimes(1);
  });
});
