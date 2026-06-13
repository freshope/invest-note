"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/base/Button";
import { createClient } from "@/lib/supabase/client";

interface UserInfoSectionProps {
  email: string;
}

export function UserInfoSection({ email }: UserInfoSectionProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [pending, setPending] = useState(false);

  async function handleSignOut() {
    setPending(true);
    const supabase = createClient();
    try {
      // 서버 호출 실패에도 로컬 세션은 무조건 비우도록 scope: "local"
      await supabase.auth.signOut({ scope: "local" });
    } catch (error) {
      console.error("[signOut]", error);
      toast.error("로그아웃 중 문제가 발생했어요. 다시 시도해주세요.");
    } finally {
      // AuthGuard에 의존하지 않고 직접 정리·이동 — 어떤 환경에서도 동일하게 동작.
      queryClient.clear();
      router.replace("/login");
      setPending(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="rounded-2xl bg-muted/60 p-5 space-y-1">
        <p className="text-[12px] font-semibold text-muted-foreground">이메일</p>
        <p className="text-[15px] font-medium text-foreground">{email}</p>
      </div>

      <div className="rounded-2xl bg-muted/60 overflow-hidden">
        <Button
          type="button"
          variant="ghost"
          className="w-full text-destructive hover:bg-destructive/10 hover:text-destructive h-12 text-[15px]"
          disabled={pending}
          onClick={handleSignOut}
        >
          {pending ? "로그아웃 중..." : "로그아웃"}
        </Button>
      </div>
    </div>
  );
}
