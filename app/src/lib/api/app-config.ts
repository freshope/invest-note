/** 강제 업데이트용 public 설정. 인증 불필요 — apiFetch 의 Bearer 토큰 경로를 타지 않는다. */
export type AppConfig = {
  minSupportedVersion: string;
  storeUrl: { ios: string; android: string };
  beAuthEnabled: boolean;
};

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

// BE OAuth flow 토글. app-config async fetch 로 오지만 auth 분기는 동기 시점이 많아
// (lib/auth 6함수) 모듈 싱글톤으로 캐시해 sync 가용성을 보장한다. fetch 성공 시에만 set,
// 미수신/실패/필드 부재 시 default false(=Supabase flow=현재 라이브) 로 fail-safe.
let beAuthEnabledCache = false;
export function setBeAuthEnabled(v: boolean): void {
  beAuthEnabledCache = v;
}
export function getBeAuthEnabled(): boolean {
  return beAuthEnabledCache;
}

export async function fetchAppConfig(): Promise<AppConfig> {
  const res = await fetch(`${API_BASE}/app-config`);
  if (!res.ok) {
    throw new Error(`app-config fetch failed: ${res.status}`);
  }
  const config = (await res.json()) as AppConfig;
  // 캐시를 채우는 유일 seam(ForceUpdateGate 가 startup 에 호출). 필드 부재→OFF.
  setBeAuthEnabled(config.beAuthEnabled ?? false);
  return config;
}
