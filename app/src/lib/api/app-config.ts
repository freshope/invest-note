/** 강제 업데이트용 public 설정. 인증 불필요 — apiFetch 의 Bearer 토큰 경로를 타지 않는다. */
export type AppConfig = {
  minSupportedVersion: string;
  storeUrl: { ios: string; android: string };
  beAuthEnabled: boolean;
};

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

// BE OAuth flow 토글. app-config async fetch 로 오지만 auth 분기(lib/auth 6함수)는 동기 시점이
// 많아 모듈 싱글톤으로 캐시해 sync 가용성을 보장한다.
//
// ⚠️ 세션 내 불변(2b-4 race fix): 첫 settle(fetch 성공 or ensureBeAuthFlagLoaded timeout) 이후
// 값을 고정한다. AuthProvider 의 subscribe()/mount getUser() 는 1회 등록·조회이므로, 그 시점에
// 본 값과 이후 caller(signInWithOAuth 등)가 본 값이 다르면 BE↔Supabase 채널 불일치로 로그인이
// 깨진다(token 은 BE listeners 로 emit 되는데 AuthProvider 는 Supabase 를 구독한 상태가 됨).
// fail-safe 기본 false(=Supabase=현재 라이브 동작).
let beAuthEnabledCache = false;
let settled = false;

function settle(value: boolean): void {
  if (settled) return;
  beAuthEnabledCache = value;
  settled = true;
}

export function getBeAuthEnabled(): boolean {
  return beAuthEnabledCache;
}

let configPromise: Promise<AppConfig> | null = null;

export function fetchAppConfig(): Promise<AppConfig> {
  // memoize: ForceUpdateGate 와 ensureBeAuthFlagLoaded 가 단일 fetch 를 공유(one fetch, one source).
  configPromise ??= (async () => {
    const res = await fetch(`${API_BASE}/app-config`);
    if (!res.ok) {
      throw new Error(`app-config fetch failed: ${res.status}`);
    }
    const config = (await res.json()) as AppConfig;
    settle(config.beAuthEnabled ?? false); // 필드 부재(구 BE)→OFF
    return config;
  })();
  return configPromise;
}

const FLAG_LOAD_TIMEOUT_MS = 3000;

/**
 * auth 초기화 직전 1회 호출. beAuthEnabled 가 동기 가용해지도록 fetch 완료(또는 timeout)까지 대기.
 * ⚠️ bounded: 오프라인 cold start 에서 무한 대기(splash hang) 금지 — timeout 시 OFF 로 세션 고정.
 * timeout/실패 후 fetch 가 늦게 도착해도 settle 가드로 값이 안 바뀐다(세션 일관).
 */
export async function ensureBeAuthFlagLoaded(
  timeoutMs = FLAG_LOAD_TIMEOUT_MS,
): Promise<void> {
  if (settled) return;
  await Promise.race([
    fetchAppConfig().catch(() => undefined), // fetch 실패해도 진행(아래 settle(false))
    new Promise<void>((resolve) => setTimeout(resolve, timeoutMs)),
  ]);
  settle(false); // 미settle(timeout/실패) 시 OFF 고정. 이미 settled 면 no-op.
}

/** 테스트 전용: 모듈 싱글톤 리셋(케이스 간 settled/configPromise 누수 차단). 프로덕션 미사용. */
export function __resetAppConfigForTest(): void {
  beAuthEnabledCache = false;
  settled = false;
  configPromise = null;
}

/** 테스트 전용: 플래그 값을 강제 settle(isBeAuthFlow 분기 테스트용). 프로덕션 미사용. */
export function __setBeAuthEnabledForTest(value: boolean): void {
  beAuthEnabledCache = value;
  settled = true;
}
