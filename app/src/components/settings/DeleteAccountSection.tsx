"use client";

import { useRef } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/base/Button";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  FullScreenPanelHeader,
  FullScreenPanelBody,
  FullScreenPanelFooter,
} from "@/components/base/FullScreenPanel";
import { SettingsMenuRow } from "@/components/settings/SettingsMenuRow";
import { useDialogState } from "@/hooks/useDialogState";
import { meApi } from "@/lib/api-client";
import { signOut } from "@/lib/auth";

export function DeleteAccountSection() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const panel = useDialogState();
  // 패널 close→재진입이 useDialogState.pending 을 리셋해도 in-flight 삭제가 두 번
  // 발사되지 않도록, 패널 상태와 분리된 잠금. 되돌릴 수 없는 작업이라 중복 호출 차단.
  const deletingRef = useRef(false);

  async function handleConfirm() {
    if (deletingRef.current) return;
    deletingRef.current = true;
    await panel.run(async () => {
      await meApi.deleteAccount();
      // 서버 호출 실패해도 로컬 세션은 비우도록 scope: "local"(signOut 내부 고정)
      try {
        await signOut();
      } catch (error) {
        console.error("[deleteAccount] signOut after delete", error);
      }
      queryClient.clear();
      toast.success("계정이 삭제되었습니다.");
      router.replace("/login");
    }, "계정 삭제에 실패했습니다. 잠시 후 다시 시도해주세요.");
    // 성공 시 router.replace 로 언마운트되므로 도달하지 않고, 실패 시에만 재시도 허용.
    deletingRef.current = false;
  }

  return (
    <>
      <SettingsMenuRow
        label="회원 탈퇴"
        variant="destructive"
        onClick={() => panel.setOpen(true)}
      />

      <FullScreenPanel open={panel.open} onOpenChange={panel.setOpen}>
        <FullScreenPanelContent>
          <FullScreenPanelHeader title="회원 탈퇴" />
          <FullScreenPanelBody>
            <div className="flex min-h-full flex-col">
              <div className="flex-1 px-5 pt-4 pb-4 space-y-4">
                <div className="rounded-2xl bg-destructive/10 p-5 space-y-2">
                  <p className="text-[15px] font-semibold text-destructive">
                    정말 탈퇴하시겠어요?
                  </p>
                  <p className="text-[13px] text-foreground/80 leading-relaxed">
                    탈퇴 시 계좌·거래 기록 등 모든 데이터가 영구적으로
                    삭제되며, 복구할 수 없습니다.
                  </p>
                </div>
                <p className="px-1 text-[13px] text-muted-foreground leading-relaxed">
                  계속 진행하시려면 아래 “탈퇴하기”를 눌러주세요.
                </p>
              </div>

              <FullScreenPanelFooter>
                {panel.error && (
                  <p className="mb-2 text-sm text-destructive">{panel.error}</p>
                )}
                <Button
                  type="button"
                  variant="destructive"
                  size="xl"
                  className="w-full"
                  disabled={panel.pending}
                  onClick={handleConfirm}
                >
                  {panel.pending ? "탈퇴 중..." : "탈퇴하기"}
                </Button>
              </FullScreenPanelFooter>
            </div>
          </FullScreenPanelBody>
        </FullScreenPanelContent>
      </FullScreenPanel>
    </>
  );
}
