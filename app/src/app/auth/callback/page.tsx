"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    let mounted = true;
    const supabase = createClient();
    const code = new URLSearchParams(window.location.search).get("code");

    if (!code) {
      router.replace("/login?error=oauth_failed");
      return;
    }

    supabase.auth
      .exchangeCodeForSession(code)
      .then(({ error }) => {
        if (!mounted) return;
        if (error) {
          router.replace("/login?error=oauth_failed");
        } else {
          router.replace("/");
        }
      });

    return () => { mounted = false; };
  }, [router]);

  return (
    <div className="flex min-h-svh items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
    </div>
  );
}
