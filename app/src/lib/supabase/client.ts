import { createClient as createSupabaseClient } from "@supabase/supabase-js";

// 정적 export + Capacitor 환경에서는 SSR 쿠키 공유가 필요 없고,
// `capacitor://localhost` 스킴에서 WebKit이 쿠키를 저장하지 않아
// 쿠키 기반 storage는 PKCE verifier를 잃는다. supabase-js 기본 동작(localStorage + PKCE)을 사용.
export function createClient() {
  return createSupabaseClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      auth: {
        flowType: "pkce",
      },
    },
  );
}
