"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/base/Button";
import { createClient } from "@/lib/supabase/client";

interface UserInfoSectionProps {
  email: string;
}

export function UserInfoSection({ email }: UserInfoSectionProps) {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function handleSignOut() {
    setPending(true);
    try {
      const supabase = createClient();
      await supabase.auth.signOut();
      router.push("/login");
    } catch {
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
