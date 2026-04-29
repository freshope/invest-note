"use client";

import { useEffect, useMemo } from "react";
import { AlertCircleIcon } from "lucide-react";
import { Button } from "@/components/base/Button";
import { BrokerLogo } from "@/components/base/BrokerLogo";
import { cn } from "@/lib/utils";
import type { Account } from "@/types/database";
import { findBrokerKeyByAccountBroker } from "./brokers";

interface Props {
  accounts: Account[];
  selectedAccountId: string;
  onSelect: (id: string) => void;
  onNext: () => void;
}

export function AccountStep({ accounts, selectedAccountId, onSelect, onNext }: Props) {
  const eligibleAccounts = useMemo(
    () => accounts.filter((a) => findBrokerKeyByAccountBroker(a.broker) !== null),
    [accounts]
  );

  useEffect(() => {
    if (selectedAccountId || eligibleAccounts.length !== 1) return;
    onSelect(eligibleAccounts[0].id);
  }, [eligibleAccounts, selectedAccountId, onSelect]);

  const isEmpty = accounts.length === 0;

  return (
    <div className="flex flex-col min-h-full">
      <div className="flex-1 px-5 pt-2 pb-4 space-y-5">
        {isEmpty ? (
          <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed p-8 text-center">
            <AlertCircleIcon className="h-6 w-6 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium">등록된 계좌가 없습니다</p>
              <p className="mt-1 text-sm text-muted-foreground">
                먼저 설정 화면에서 계좌를 등록한 뒤 다시 시도해주세요.
              </p>
            </div>
          </div>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">
              거래를 등록할 계좌를 선택하세요. 선택한 계좌의 증권사 형식으로 파일을 분석합니다.
            </p>

            <div className="flex flex-col gap-2">
              {accounts.map((a) => {
                const supported = findBrokerKeyByAccountBroker(a.broker) !== null;
                const selected = a.id === selectedAccountId;
                return (
                  <button
                    key={a.id}
                    type="button"
                    disabled={!supported}
                    onClick={() => supported && onSelect(a.id)}
                    className={cn(
                      "flex items-center gap-3 rounded-lg border p-3 text-left transition-colors",
                      !supported && "cursor-not-allowed bg-muted/30 opacity-60",
                      supported && selected && "border-primary bg-primary/5",
                      supported && !selected && "hover:bg-accent"
                    )}
                  >
                    <BrokerLogo broker={a.broker} size={36} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{a.name}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {a.broker ?? "증권사 미설정"}
                        {!supported && " · 일괄 등록 미지원"}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          </>
        )}
      </div>

      <div
        className="sticky bottom-0 bg-background px-5 pt-3 pb-4"
        style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }}
      >
        <Button
          size="xl"
          className="w-full"
          onClick={onNext}
          disabled={!selectedAccountId}
        >
          다음
        </Button>
      </div>
    </div>
  );
}
