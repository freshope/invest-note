"use client";

import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import { Button } from "@/components/base/Button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/base/Dialog";
import { deleteAccount } from "@/app/(app)/settings/actions";

interface DeleteAccountDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  accountId: string;
  accountName: string;
}

function DeleteButton() {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" variant="destructive" disabled={pending}>
      {pending ? "삭제 중..." : "삭제"}
    </Button>
  );
}

export function DeleteAccountDialog({
  open,
  onOpenChange,
  accountId,
  accountName,
}: DeleteAccountDialogProps) {
  const [state, formAction] = useActionState(deleteAccount, undefined);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>계좌 삭제</DialogTitle>
          <DialogDescription>
            <strong>{accountName}</strong>을(를) 삭제하시겠습니까?
            <br />
            이 작업은 되돌릴 수 없습니다.
          </DialogDescription>
        </DialogHeader>

        {state?.error && (
          <p className="text-sm text-destructive">{state.error}</p>
        )}

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            취소
          </Button>
          <form action={formAction}>
            <input type="hidden" name="id" value={accountId} />
            <DeleteButton />
          </form>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
