// 네이티브 전용 secure 토큰 store. iOS Keychain / Android Keystore 백킹
// (@aparajita/capacitor-secure-storage). 평문 localStorage 금지(C5, 금융 앱).
//
// 웹 분기는 이 모듈을 쓰지 않는다(Supabase 가 자체 persistence). isNativePlatform
// 게이트는 lib/auth/index 가 담당하므로 여기선 무조건 secure storage 를 호출한다.
import { SecureStorage } from "@aparajita/capacitor-secure-storage";

const ACCESS_KEY = "auth.access_token";
const REFRESH_KEY = "auth.refresh_token";
// PKCE verifier: 딥링크 cold-start 생존을 위해 메모리 아닌 secure storage 임시 보관(C2).
// 교환 성공/실패 후 clearVerifier 로 삭제.
const VERIFIER_KEY = "auth.pkce_verifier";

export async function saveTokens(tokens: {
  access: string;
  refresh: string;
}): Promise<void> {
  await SecureStorage.setItem(ACCESS_KEY, tokens.access);
  await SecureStorage.setItem(REFRESH_KEY, tokens.refresh);
}

export async function getAccessTokenRaw(): Promise<string | null> {
  return SecureStorage.getItem(ACCESS_KEY);
}

export async function getRefreshToken(): Promise<string | null> {
  return SecureStorage.getItem(REFRESH_KEY);
}

export async function clearTokens(): Promise<void> {
  await SecureStorage.remove(ACCESS_KEY);
  await SecureStorage.remove(REFRESH_KEY);
}

export async function saveVerifier(verifier: string): Promise<void> {
  await SecureStorage.setItem(VERIFIER_KEY, verifier);
}

export async function getVerifier(): Promise<string | null> {
  return SecureStorage.getItem(VERIFIER_KEY);
}

export async function clearVerifier(): Promise<void> {
  await SecureStorage.remove(VERIFIER_KEY);
}
