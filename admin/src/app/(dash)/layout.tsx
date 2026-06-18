"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/providers/AuthProvider";
import { signOut } from "@/lib/auth";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";

// 클라이언트 가드(static-export SPA, middleware 미사용).
// 세션 존재 + allowlist(admin) 여부를 함께 확인한다. 클라이언트는 ADMIN_EMAILS 를 모르므로
// BE /admin/me(require_admin) 프로브 결과(isAdmin)로 셸 진입을 막는다. 데이터 API 의
// require_admin(403)이 최종 방어선이지만, 비-admin 은 진입 자체를 차단한다(접근 권한 없음 화면).
// 비-admin 을 /login 으로 보내면 login 이 인증 세션을 보고 다시 / 로 돌려보내 무한 루프가 되므로,
// 리다이렉트 대신 명시적 거부 화면 + 로그아웃을 노출한다.
export default function DashLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading, isAdmin } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login/");
    }
  }, [loading, user, router]);

  // 세션 없음 / 로딩 / admin 프로브 진행 중(isAdmin === null)에는 로딩 표시.
  if (loading || !user || isAdmin === null) {
    return (
      <div className="flex min-h-svh items-center justify-center bg-background">
        <p className="text-sm text-muted-foreground">불러오는 중...</p>
      </div>
    );
  }

  // 로그인은 됐으나 allowlist 밖 — 셸 진입 차단(리다이렉트 금지: login 루프 회피).
  if (isAdmin === false) {
    return (
      <div className="flex min-h-svh flex-col items-center justify-center gap-4 bg-background px-5 text-center">
        <div>
          <h1 className="text-lg font-semibold text-foreground">
            접근 권한 없음
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            이 계정은 어드민 권한이 없습니다.
          </p>
        </div>
        <button
          type="button"
          onClick={() => signOut()}
          className="h-10 rounded-lg border border-border bg-background px-4 text-sm font-medium text-foreground transition-opacity hover:bg-muted"
        >
          로그아웃
        </button>
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
