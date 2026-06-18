// ⚠️ Supabase 격리 경계: @supabase/supabase-js 를 import 하는 유일한 파일군(lib/auth/)이다.
// 다른 어떤 컴포넌트·lib·페이지도 supabase-js 를 직접 import 하지 않는다.
// 탈-Supabase 시 lib/auth/ 의 구현만 교체한다.
import { createClient as createSupabaseClient } from "@supabase/supabase-js";

// app 과 동일: 정적 export + 브라우저 환경에서 localStorage + PKCE 사용.
// 싱글톤으로 유지해 GoTrueClient 중복 경고 방지.
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
