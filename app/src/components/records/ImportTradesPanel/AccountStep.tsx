"use client";

import { AlertCircleIcon } from "lucide-react";
import { Button } from "@/components/base/Button";
import { BrokerLogo } from "@/components/base/BrokerLogo";
import { FullScreenPanelFooter } from "@/components/base/FullScreenPanel";
import { cn } from "@/lib/utils";
import type { Account } from "@/types/database";
import { findBrokerKeyByAccountBroker } from "./brokers";

interface Props {
  accounts: Account[];
  selectedAccountId: string;
  onSelect: (id: string) => void;
  onNext: () => void;
  /** 미지원 계좌 행에서 거래내역서 제보 진입. */
  onReportUnsupported: (account: Account) => void;
}

export function AccountStep({
  accounts,
  selectedAccountId,
  onSelect,
  onNext,
  onReportUnsupported,
}: Props) {
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
                if (!supported) {
                  return (
                    <div
                      key={a.id}
                      className="rounded-lg border bg-muted/30 p-3"
                    >
                      <div className="flex items-center gap-3 opacity-60">
                        <BrokerLogo broker={a.broker} size={36} />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium">{a.name}</p>
                          <p className="truncate text-xs text-muted-foreground">
                            {a.broker ?? "증권사 미설정"} · 일괄 등록 미지원
                          </p>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => onReportUnsupported(a)}
                        className="mt-2 w-full rounded-md border border-primary/40 py-2 text-xs font-medium text-primary transition-colors hover:bg-primary/5"
                      >
                        거래내역서 제보하기
                      </button>
                    </div>
                  );
                }
                return (
                  <button
                    key={a.id}
                    type="button"
                    onClick={() => onSelect(a.id)}
                    className={cn(
                      "flex items-center gap-3 rounded-lg border p-3 text-left transition-colors",
                      selected && "border-primary bg-primary/5",
                      !selected && "hover:bg-accent"
                    )}
                  >
                    <BrokerLogo broker={a.broker} size={36} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{a.name}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {a.broker ?? "증권사 미설정"}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          </>
        )}
      </div>

      <FullScreenPanelFooter>
        <Button
          size="xl"
          className="w-full"
          onClick={onNext}
          disabled={!selectedAccountId}
        >
          다음
        </Button>
      </FullScreenPanelFooter>
    </div>
  );
}
