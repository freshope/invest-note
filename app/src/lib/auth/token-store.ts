// 토큰 store — platform 분기. 네이티브 = iOS Keychain / Android Keystore secure storage
// (@aparajita/capacitor-secure-storage), 웹 = localStorage(개발 편의용 웹 BE flow).
//
// ⚠️ C5 보안 근거(웹 localStorage 토큰 허용 — 평문 localStorage 금지 규칙의 명시적 예외):
//   ⓐ 운영 웹은 dormant(`be_app_web_redirect_url` 빈 값 → BE 503) — 웹 로그인 자체가 비활성.
//   ⓑ 웹은 배포 타깃 아님([[project_deploy_targets]], Capacitor 단일) — 개발 편의용 경로.
//   ⓒ 어드민(admin/)이 동일 선례(내부 콘솔, web localStorage).
//   → **네이티브는 secure storage 불변**(금융 앱 본체). 웹 localStorage 는 dev 한정 trade-off.
//
// G9: 네이티브 플러그인을 top-level 정적 import 하면 @/lib/auth 를 import 하는 모든
// 코드(login·AuthProvider·api-client)의 웹 번들 그래프에 끌려 들어온다. 네이티브 분기
// 안에서만 `await import(...)` lazy idiom 으로 격리한다(웹 번들 미포함).
//
// ⚠️ SecureStorage 는 Capacitor proxy(thenable 처럼 보임 — 임의 속성 접근이 네이티브
// 메서드 호출로 브릿지)다. 이를 Promise 의 resolve 값으로 내보내면(`then(m => m.SecureStorage)`)
// Promise resolution 이 thenable 검사로 `SecureStorage.then()` 을 호출 → iOS 네이티브에
// `then` 미구현 → reject/hang(디바이스에서만 발현, jsdom mock 은 통과). 따라서 **module
// namespace(thenable 아님)를 캐시·반환**하고 호출부에서 sync 로 SecureStorage 를 꺼낸다.
import { isNativePlatform } from "@/lib/platform";

type SecureStorageNS = typeof import("@aparajita/capacitor-secure-storage");

let modulePromise: Promise<SecureStorageNS> | null = null;

function loadModule(): Promise<SecureStorageNS> {
  modulePromise ??= import("@aparajita/capacitor-secure-storage");
  return modulePromise;
}

// 키는 네이티브·웹·어드민 공통 네이밍.
const ACCESS_KEY = "auth.access_token";
const REFRESH_KEY = "auth.refresh_token";
// PKCE verifier: 딥링크 cold-start(네이티브)·full-page redirect 왕복(웹) 생존을 위해
// 메모리 아닌 영속 store 임시 보관(C2). 교환 성공/실패 후 clearVerifier 로 삭제.
const VERIFIER_KEY = "auth.pkce_verifier";

// 웹 localStorage 접근이 throw 하는 환경(Safari private mode·storage 비활성·sandbox)에서
// read 는 로그아웃 상태(null)로 graceful 폴백한다(throw 전파 시 Bearer 주입 경로가 깨짐).
function safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export async function saveTokens(tokens: {
  access: string;
  refresh: string;
}): Promise<void> {
  if (isNativePlatform()) {
    const { SecureStorage } = await loadModule();
    // 독립 setItem 2회 병렬(G5/F#3).
    await Promise.all([
      SecureStorage.setItem(ACCESS_KEY, tokens.access),
      SecureStorage.setItem(REFRESH_KEY, tokens.refresh),
    ]);
    return;
  }
  localStorage.setItem(ACCESS_KEY, tokens.access);
  localStorage.setItem(REFRESH_KEY, tokens.refresh);
}

export async function getAccessTokenRaw(): Promise<string | null> {
  if (isNativePlatform()) {
    const { SecureStorage } = await loadModule();
    return SecureStorage.getItem(ACCESS_KEY) as Promise<string | null>;
  }
  return safeGet(ACCESS_KEY);
}

export async function getRefreshToken(): Promise<string | null> {
  if (isNativePlatform()) {
    const { SecureStorage } = await loadModule();
    return SecureStorage.getItem(REFRESH_KEY) as Promise<string | null>;
  }
  return safeGet(REFRESH_KEY);
}

export async function clearTokens(): Promise<void> {
  if (isNativePlatform()) {
    const { SecureStorage } = await loadModule();
    await Promise.all([
      SecureStorage.remove(ACCESS_KEY),
      SecureStorage.remove(REFRESH_KEY),
    ]);
    return;
  }
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

export async function saveVerifier(verifier: string): Promise<void> {
  if (isNativePlatform()) {
    const { SecureStorage } = await loadModule();
    await SecureStorage.setItem(VERIFIER_KEY, verifier);
    return;
  }
  localStorage.setItem(VERIFIER_KEY, verifier);
}

export async function getVerifier(): Promise<string | null> {
  if (isNativePlatform()) {
    const { SecureStorage } = await loadModule();
    return SecureStorage.getItem(VERIFIER_KEY) as Promise<string | null>;
  }
  return safeGet(VERIFIER_KEY);
}

export async function clearVerifier(): Promise<void> {
  if (isNativePlatform()) {
    const { SecureStorage } = await loadModule();
    await SecureStorage.remove(VERIFIER_KEY);
    return;
  }
  localStorage.removeItem(VERIFIER_KEY);
}
