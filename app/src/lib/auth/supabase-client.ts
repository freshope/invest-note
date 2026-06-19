// ⚠️ Supabase 격리 경계: @supabase/supabase-js 를 import 하는 유일한 파일이다.
// 다른 어떤 컴포넌트·lib·페이지도 supabase-js 를 직접 import 하지 않는다.
// 탈-Supabase 시 lib/auth/ 의 구현만 교체한다.
import { createClient as createSupabaseClient } from "@supabase/supabase-js";

// 정적 export + Capacitor 환경에서는 SSR 쿠키 공유가 필요 없고,
// `capacitor://localhost` 스킴에서 WebKit이 쿠키를 저장하지 않아
// 쿠키 기반 storage는 PKCE verifier를 잃는다. supabase-js 기본 동작(localStorage + PKCE)을 사용.
// 싱글톤으로 유지해 GoTrueClient 중복 경고 방지
let client: ReturnType<typeof createSupabaseClient> | null = null;

export function getSupabaseClient() {
  if (!client) {
    client = createSupabaseClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
      {
        auth: {
          flowType: "pkce",
        },
      },
    );
  }
  return client;
}
