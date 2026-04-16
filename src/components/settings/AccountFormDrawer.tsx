"use client";

import { useActionState, useEffect, useRef, useState } from "react";
import { useFormStatus } from "react-dom";
import { Button } from "@/components/base/Button";
import { Input } from "@/components/base/Input";
import { Label } from "@/components/base/Label";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/base/Drawer";
import { createAccount, updateAccount } from "@/app/(app)/settings/actions";
import { cn } from "@/lib/utils";
import type { Account } from "@/types/database";

const BROKERS = [
  { name: "키움증권", short: "키움", color: "bg-orange-500" },
  { name: "미래에셋증권", short: "미래", color: "bg-blue-600" },
  { name: "NH투자증권", short: "NH", color: "bg-green-600" },
  { name: "삼성증권", short: "삼성", color: "bg-blue-800" },
  { name: "KB증권", short: "KB", color: "bg-amber-500" },
  { name: "한국투자증권", short: "한투", color: "bg-sky-600" },
  { name: "대신증권", short: "대신", color: "bg-red-600" },
  { name: "신한투자증권", short: "신한", color: "bg-indigo-500" },
  { name: "메리츠증권", short: "메리츠", color: "bg-teal-600" },
  { name: "하나증권", short: "하나", color: "bg-emerald-500" },
  { name: "토스증권", short: "토스", color: "bg-blue-500" },
];

interface AccountFormDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  account?: Account;
}

function SubmitButton({ label }: { label: string }) {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" disabled={pending} className="w-full">
      {pending ? "저장 중..." : label}
    </Button>
  );
}

export function AccountFormDrawer({
  open,
  onOpenChange,
  account,
}: AccountFormDrawerProps) {
  const isEdit = !!account;
  const action = isEdit ? updateAccount : createAccount;

  const [state, formAction] = useActionState(action, undefined);
  const formRef = useRef<HTMLFormElement>(null);
  const [selectedBroker, setSelectedBroker] = useState<string>(account?.broker ?? "");

  useEffect(() => {
    setSelectedBroker(account?.broker ?? "");
  }, [account]);

  useEffect(() => {
    if (state?.success) {
      onOpenChange(false);
      formRef.current?.reset();
      setSelectedBroker("");
    }
  }, [state, onOpenChange]);

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent>
        <DrawerHeader>
          <DrawerTitle>{isEdit ? "계좌 수정" : "계좌 추가"}</DrawerTitle>
        </DrawerHeader>

        <form ref={formRef} action={formAction} className="px-5 pb-4 space-y-5">
          {isEdit && (
            <input type="hidden" name="id" value={account.id} />
          )}

          <div className="space-y-1.5">
            <Label htmlFor="name">
              계좌명 <span className="text-destructive">*</span>
            </Label>
            <Input
              id="name"
              name="name"
              placeholder="예: 키움증권 위탁계좌"
              defaultValue={account?.name ?? ""}
              maxLength={50}
              required
            />
          </div>

          <div className="space-y-1.5">
            <Label>증권사</Label>
            <input type="hidden" name="broker" value={selectedBroker} />
            <div className="grid grid-cols-3 gap-2">
              {BROKERS.map((broker) => {
                const isSelected = selectedBroker === broker.name;
                return (
                  <button
                    key={broker.name}
                    type="button"
                    onClick={() =>
                      setSelectedBroker(isSelected ? "" : broker.name)
                    }
                    className={cn(
                      "flex flex-col items-center gap-1.5 rounded-xl border p-3 text-center transition-colors",
                      isSelected
                        ? "border-primary bg-primary/5 ring-2 ring-primary ring-offset-1"
                        : "border-border hover:bg-muted/50"
                    )}
                  >
                    <span
                      className={cn(
                        "flex h-9 w-9 items-center justify-center rounded-full text-xs font-bold text-white",
                        broker.color
                      )}
                    >
                      {broker.short}
                    </span>
                    <span className="text-xs leading-tight text-foreground">
                      {broker.name}
                    </span>
                  </button>
                );
              })}
            </div>
            {selectedBroker && (
              <p className="text-xs text-muted-foreground">
                선택됨: {selectedBroker}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="cash_balance">예수금 (원)</Label>
            <Input
              id="cash_balance"
              name="cash_balance"
              type="number"
              inputMode="numeric"
              placeholder="0"
              defaultValue={account ? Number(account.cash_balance) : ""}
              min={0}
              step={1}
            />
          </div>

          {state?.error && (
            <p className="text-sm text-destructive">{state.error}</p>
          )}

          <div className="pt-2">
            <SubmitButton label={isEdit ? "수정하기" : "추가하기"} />
          </div>
        </form>
      </DrawerContent>
    </Drawer>
  );
}
