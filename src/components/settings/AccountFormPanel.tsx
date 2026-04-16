"use client";

import { useActionState, useEffect, useRef, useState } from "react";
import { useFormStatus } from "react-dom";
import { Button } from "@/components/base/Button";
import { Input } from "@/components/base/Input";
import { Label } from "@/components/base/Label";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  FullScreenPanelHeader,
  FullScreenPanelBody,
} from "@/components/common/full-screen-panel";
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

interface AccountFormPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  account?: Account;
}

function SubmitButton({ label }: { label: string }) {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" size="xl" disabled={pending} className="w-full">
      {pending ? "저장 중..." : label}
    </Button>
  );
}

function formatNumber(value: number | string): string {
  const num = typeof value === "string" ? value.replace(/[^0-9]/g, "") : String(value);
  if (!num) return "";
  return Number(num).toLocaleString("ko-KR");
}

export function AccountFormPanel({
  open,
  onOpenChange,
  account,
}: AccountFormPanelProps) {
  const isEdit = !!account;
  const action = isEdit ? updateAccount : createAccount;

  const [state, formAction] = useActionState(action, undefined);
  const formRef = useRef<HTMLFormElement>(null);
  const [selectedBroker, setSelectedBroker] = useState<string>(account?.broker ?? "");
  const [cashDisplay, setCashDisplay] = useState<string>(
    account?.cash_balance ? formatNumber(Number(account.cash_balance)) : ""
  );

  useEffect(() => {
    setSelectedBroker(account?.broker ?? "");
    setCashDisplay(account?.cash_balance ? formatNumber(Number(account.cash_balance)) : "");
  }, [account]);

  useEffect(() => {
    if (state?.success) {
      onOpenChange(false);
      formRef.current?.reset();
      setSelectedBroker("");
      setCashDisplay("");
    }
  }, [state, onOpenChange]);

  function handleCashChange(e: React.ChangeEvent<HTMLInputElement>) {
    const digits = e.target.value.replace(/[^0-9]/g, "");
    setCashDisplay(digits ? Number(digits).toLocaleString("ko-KR") : "");
  }

  return (
    <FullScreenPanel open={open} onOpenChange={onOpenChange}>
      <FullScreenPanelContent open={open}>
        <FullScreenPanelHeader title={isEdit ? "계좌 수정" : "계좌 추가"} />

        <FullScreenPanelBody>
          <form ref={formRef} action={formAction} className="flex flex-col min-h-full">
            <div className="flex-1 px-5 pt-2 pb-4 space-y-5">
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

              </div>

              <div className="space-y-1.5">
                <Label htmlFor="cash_balance">예수금 (원)</Label>
                <input
                  type="hidden"
                  name="cash_balance"
                  value={cashDisplay.replace(/,/g, "")}
                />
                <Input
                  id="cash_balance"
                  type="text"
                  inputMode="numeric"
                  placeholder="0"
                  value={cashDisplay}
                  onChange={handleCashChange}
                />
              </div>

              {state?.error && (
                <p className="text-sm text-destructive">{state.error}</p>
              )}
            </div>

            {/* 하단 고정 제출 버튼 */}
            <div
              className="sticky bottom-0 bg-background px-5 pt-3 pb-4"
              style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }}
            >
              <SubmitButton label={isEdit ? "수정하기" : "추가하기"} />
            </div>
          </form>
        </FullScreenPanelBody>
      </FullScreenPanelContent>
    </FullScreenPanel>
  );
}
