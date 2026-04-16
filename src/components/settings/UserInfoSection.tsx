"use client";

import { useFormStatus } from "react-dom";
import { Button } from "@/components/base/Button";
import { signOut } from "@/app/(app)/settings/actions";

function LogoutButton() {
  const { pending } = useFormStatus();
  return (
    <Button
      type="submit"
      variant="ghost"
      className="w-full text-destructive hover:bg-destructive/10 hover:text-destructive h-12 text-[15px]"
      disabled={pending}
    >
      {pending ? "로그아웃 중..." : "로그아웃"}
    </Button>
  );
}

interface UserInfoSectionProps {
  email: string;
}

export function UserInfoSection({ email }: UserInfoSectionProps) {
  return (
    <div className="space-y-3">
      <div className="rounded-2xl bg-muted/60 p-5 space-y-1">
        <p className="text-[12px] font-semibold text-muted-foreground">이메일</p>
        <p className="text-[15px] font-medium text-foreground">{email}</p>
      </div>

      <div className="rounded-2xl bg-muted/60 overflow-hidden">
        <form action={signOut}>
          <LogoutButton />
        </form>
      </div>
    </div>
  );
}
