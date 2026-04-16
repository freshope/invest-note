"use client";

import { useTransition, useState } from "react";
import { Button } from "@/components/base/Button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/base/Dialog";
import { deleteTrade } from "@/app/(app)/records/actions";

interface DeleteTradeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tradeId: string;
  assetName: string;
  onDeleted?: () => void;
}

export function DeleteTradeDialog({
  open,
  onOpenChange,
  tradeId,
  assetName,
  onDeleted,
}: DeleteTradeDialogProps) {
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState("");

  function handleDelete() {
    setError("");
    startTransition(async () => {
      const result = await deleteTrade(tradeId);
      if (result.error) {
        setError(result.error);
      } else {
        onOpenChange(false);
        onDeleted?.();
      }
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>거래 삭제</DialogTitle>
          <DialogDescription>
            <strong>{assetName}</strong> 거래 기록을 삭제하시겠습니까?
            <br />
            이 작업은 되돌릴 수 없습니다.
          </DialogDescription>
        </DialogHeader>

        {error && <p className="text-sm text-destructive px-1">{error}</p>}

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isPending}
          >
            취소
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={handleDelete}
            disabled={isPending}
          >
            {isPending ? "삭제 중..." : "삭제"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
