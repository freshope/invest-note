"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/base/Button";
import { ConfirmDeleteDialog } from "@/components/shared/ConfirmDeleteDialog";
import { useDialogState } from "@/hooks/useDialogState";
import { meApi } from "@/lib/api-client";
import { createClient } from "@/lib/supabase/client";

export function DeleteAccountSection() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const dialog = useDialogState();
  const [opening, setOpening] = useState(false);

  function handleOpen() {
    // pending 상태에서도 카드 자체는 닫히지 않도록 잠금
    if (dialog.pending) return;
    setOpening(true);
    dialog.setOpen(true);
    setOpening(false);
  }

  async function handleConfirm() {
    await dialog.run(async () => {
      await meApi.deleteAccount();
      const supabase = createClient();
      // 서버 호출 실패해도 로컬 세션은 비우도록 scope: "local"
      try {
        await supabase.auth.signOut({ scope: "local" });
      } catch (error) {
        console.error("[deleteAccount] signOut after delete", error);
      }
      queryClient.clear();
      toast.success("계정이 삭제되었습니다.");
      router.replace("/login");
    }, "계정 삭제에 실패했습니다. 잠시 후 다시 시도해주세요.");
  }

  return (
    <div className="space-y-3">
      <div className="rounded-2xl bg-muted/60 p-5 space-y-2">
        <p className="text-[13px] font-semibold text-foreground">회원 탈퇴</p>
        <p className="text-[12px] text-muted-foreground leading-relaxed">
          탈퇴 시 계좌·거래 기록 등 모든 데이터가 영구적으로 삭제되며,
          복구할 수 없습니다.
        </p>
      </div>

      <div className="rounded-2xl bg-muted/60 overflow-hidden">
        <Button
          type="button"
          variant="ghost"
          className="w-full text-destructive hover:bg-destructive/10 hover:text-destructive h-12 text-[15px]"
          disabled={opening || dialog.pending}
          onClick={handleOpen}
        >
          회원 탈퇴
        </Button>
      </div>

      <ConfirmDeleteDialog
        open={dialog.open}
        onOpenChange={dialog.setOpen}
        title="정말 탈퇴하시겠어요?"
        description={
          <>
            모든 계좌와 거래 기록이 영구적으로 삭제되며 복구할 수 없습니다.
            <br />
            계속 진행하시려면 “탈퇴”를 눌러주세요.
          </>
        }
        pending={dialog.pending}
        error={dialog.error}
        onConfirm={handleConfirm}
        confirmLabel="탈퇴"
        pendingLabel="탈퇴 중..."
      />
    </div>
  );
}
