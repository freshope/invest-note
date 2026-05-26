/** 강제 업데이트용 public 설정. 인증 불필요 — apiFetch 의 Bearer 토큰 경로를 타지 않는다. */
export type AppConfig = {
  minSupportedVersion: string;
  storeUrl: { ios: string; android: string };
};

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

export async function fetchAppConfig(): Promise<AppConfig> {
  const res = await fetch(`${API_BASE}/app-config`);
  if (!res.ok) {
    throw new Error(`app-config fetch failed: ${res.status}`);
  }
  return res.json() as Promise<AppConfig>;
}
