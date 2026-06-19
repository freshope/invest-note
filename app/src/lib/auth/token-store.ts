// 네이티브 전용 secure 토큰 store. iOS Keychain / Android Keystore 백킹
// (@aparajita/capacitor-secure-storage). 평문 localStorage 금지(C5, 금융 앱).
//
// 웹 분기는 이 모듈을 쓰지 않는다(Supabase 가 자체 persistence). isNativePlatform
// 게이트는 lib/auth/index 가 담당하므로 여기선 무조건 secure storage 를 호출한다.
//
// G9: 네이티브 플러그인을 top-level 정적 import 하면 @/lib/auth 를 import 하는 모든
// 웹 코드(login·AuthProvider·api-client)의 웹 번들 그래프에 끌려 들어온다(Phase1 격리
// invariant 위반). 딥링크 핸들러와 동일한 `await import(...)` lazy idiom 으로 격리한다.

type SecureStorageModule =
  typeof import("@aparajita/capacitor-secure-storage")["SecureStorage"];

let secureStoragePromise: Promise<SecureStorageModule> | null = null;

function loadSecureStorage(): Promise<SecureStorageModule> {
  secureStoragePromise ??= import("@aparajita/capacitor-secure-storage").then(
    (m) => m.SecureStorage,
  );
  return secureStoragePromise;
}

const ACCESS_KEY = "auth.access_token";
const REFRESH_KEY = "auth.refresh_token";
// PKCE verifier: 딥링크 cold-start 생존을 위해 메모리 아닌 secure storage 임시 보관(C2).
// 교환 성공/실패 후 clearVerifier 로 삭제.
const VERIFIER_KEY = "auth.pkce_verifier";

export async function saveTokens(tokens: {
  access: string;
  refresh: string;
}): Promise<void> {
  const storage = await loadSecureStorage();
  // 독립 setItem 2회 병렬(G5/F#3).
  await Promise.all([
    storage.setItem(ACCESS_KEY, tokens.access),
    storage.setItem(REFRESH_KEY, tokens.refresh),
  ]);
}

export async function getAccessTokenRaw(): Promise<string | null> {
  const storage = await loadSecureStorage();
  return storage.getItem(ACCESS_KEY);
}

export async function getRefreshToken(): Promise<string | null> {
  const storage = await loadSecureStorage();
  return storage.getItem(REFRESH_KEY);
}

export async function clearTokens(): Promise<void> {
  const storage = await loadSecureStorage();
  await Promise.all([
    storage.remove(ACCESS_KEY),
    storage.remove(REFRESH_KEY),
  ]);
}

export async function saveVerifier(verifier: string): Promise<void> {
  const storage = await loadSecureStorage();
  await storage.setItem(VERIFIER_KEY, verifier);
}

export async function getVerifier(): Promise<string | null> {
  const storage = await loadSecureStorage();
  return storage.getItem(VERIFIER_KEY);
}

export async function clearVerifier(): Promise<void> {
  const storage = await loadSecureStorage();
  await storage.remove(VERIFIER_KEY);
}
