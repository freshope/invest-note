"use client";

import { useAuth } from "@/components/providers/AuthProvider";
import { signOut } from "@/lib/auth";
import { Button } from "@/components/base/Button";

export function Topbar() {
  const { user } = useAuth();

  return (
    <header className="flex h-14 items-center justify-end gap-3 border-b border-border px-6">
      <span className="text-[13px] text-muted-foreground">{user?.email}</span>
      <Button variant="outline" size="sm" onClick={() => void signOut()}>
        로그아웃
      </Button>
    </header>
  );
}
