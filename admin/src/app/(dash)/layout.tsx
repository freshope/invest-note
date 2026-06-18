"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/providers/AuthProvider";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";

// 클라이언트 가드(static-export SPA, middleware 미사용).
// 여기서는 세션 존재만 확인한다 — 클라이언트는 ADMIN_EMAILS 를 모르므로 allowlist 를 강제할 수 없고,
// 실제 비-admin 차단은 API 의 require_admin(403)이 담당한다(spec 목표 #2).
// 따라서 로그인은 됐지만 allowlist 밖인 사용자는 셸에 진입하되 데이터 호출이 전부 403 으로 떨어진다.
export default function DashLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login/");
    }
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="flex min-h-svh items-center justify-center bg-background">
        <p className="text-sm text-muted-foreground">불러오는 중...</p>
      </div>
    );
  }

  return (
    <div className="flex">
      <Sidebar />
      <div className="flex min-h-svh flex-1 flex-col">
        <Topbar />
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
}
