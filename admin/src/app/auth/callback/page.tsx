"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/providers/AuthProvider";

// OAuth 콜백: Supabase JS 가 URL 의 코드를 세션으로 교환하면 AuthProvider 가
// 로그인 상태를 감지한다. 그 후 대시보드(또는 실패 시 로그인)로 리다이렉트.
export default function AuthCallbackPage() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading) {
      router.replace(user ? "/" : "/login/?error=oauth");
    }
  }, [loading, user, router]);

  return (
    <div className="flex min-h-svh items-center justify-center bg-background">
      <p className="text-sm text-muted-foreground">로그인 처리 중...</p>
    </div>
  );
}
