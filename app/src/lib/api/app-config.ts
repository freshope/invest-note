/** 강제 업데이트용 public 설정. 인증 불필요 — apiFetch 의 Bearer 토큰 경로를 타지 않는다. */
export type AppConfig = {
  minSupportedVersion: string;
  storeUrl: { ios: string; android: string };
};

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

let configPromise: Promise<AppConfig> | null = null;

export function fetchAppConfig(): Promise<AppConfig> {
  // memoize: ForceUpdateGate 와 useUpdateRequired 가 단일 fetch 를 공유(one fetch, one source).
  configPromise ??= (async () => {
    const res = await fetch(`${API_BASE}/app-config`);
    if (!res.ok) {
      throw new Error(`app-config fetch failed: ${res.status}`);
    }
    return (await res.json()) as AppConfig;
  })();
  return configPromise;
}

/** 테스트 전용: 메모이즈된 configPromise 리셋(케이스 간 누수 차단). 프로덕션 미사용. */
export function __resetAppConfigForTest(): void {
  configPromise = null;
}
