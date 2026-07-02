"use client";

import { AlertCircleIcon, CheckCircle2Icon, CheckIcon, InfoIcon, PlusIcon } from "lucide-react";
import { Button } from "@/components/base/Button";
import { BrokerLogo } from "@/components/base/BrokerLogo";
import { FullScreenPanelFooter } from "@/components/base/FullScreenPanel";
import { normalizeAccountNumber } from "@/lib/account";
import { cn } from "@/lib/utils";
import { SEMANTIC_COLORS } from "@/lib/constants/semantic-colors";
import type { Account } from "@/types/database";

// 신규 등록 카드를 나타내는 sentinel 선택값 — 실제 계좌 id 와 충돌하지 않는 문자열.
export const NEW_ACCOUNT_ID = "__new__";

interface Props {
  accounts: Account[];
  /** 현재 강조(선택)된 카드 — 계좌 id 또는 NEW_ACCOUNT_ID. */
  selectedId: string;
  onSelect: (id: string) => void;
  /** 파일 계좌번호와 자동매칭된 계좌 id(있으면 그 카드에 "자동 매칭" 배지). */
  matchedAccountId: string | null;
  /** 파일에서 추출한 계좌번호(hint) 원문. 매칭 안내·신규 카드 표시용. */
  accountHint: string | null;
  /** 신규 등록 카드의 기본 계좌명 미리보기(fallback "{증권사} {뒤4자리}"). */
  computedAccountName: string;
  /** 신규 카드 로고용 증권사명. */
  brokerLabel: string;
  onNext: () => void;
  onBack: () => void;
  isLoading: boolean;
}

// import 흐름의 계좌 선택 스텝 — 계좌 카드 목록 + "신규 등록" 카드 중 하나를 고른다.
// 순수 presentational: 선택/확정/뒤로만 상향 콜백. 재-preview·hint 자동기입은 index 가 담당.
export function AccountSelectStep({
  accounts,
  selectedId,
  onSelect,
  matchedAccountId,
  accountHint,
  computedAccountName,
  brokerLabel,
  onNext,
  onBack,
  isLoading,
}: Props) {
  const normalizedHint = normalizeAccountNumber(accountHint);
  const hasAccounts = accounts.length > 0;

  // 매칭 안내 배너: 자동매칭 있음 / 힌트 있으나 매칭 없음 / 힌트 없음.
  const matchState: "matched" | "unmatched" | "no-hint" = matchedAccountId
    ? "matched"
    : normalizedHint
      ? "unmatched"
      : "no-hint";

  // 선택한 기존 계좌의 계좌번호가 파일 힌트와 어긋나면 경고(mis-route 방지). 번호 없는 계좌는 확인 불가라 제외.
  const selectedAccount = accounts.find((a) => a.id === selectedId);
  const selectedNumber = normalizeAccountNumber(selectedAccount?.account_number);
  const hintMismatch = !!normalizedHint && !!selectedNumber && selectedNumber !== normalizedHint;

  return (
    <div className="flex flex-col min-h-full">
      <div className="flex-1 px-5 pt-2 pb-4 space-y-4">
        <p className="text-sm text-muted-foreground">
          이 거래내역서를 등록할 계좌를 선택하세요.<br />
          {normalizedHint && (
            <>
              {" "}
              <span className="font-medium text-foreground">
                파일 계좌번호 {accountHint}
              </span>
            </>
          )}
        </p>

        {hasAccounts && matchState === "matched" && (
          <div className={cn("flex items-start gap-2 rounded-lg border px-3 py-2 text-xs", SEMANTIC_COLORS.success.bgSoft, SEMANTIC_COLORS.success.borderSoft, SEMANTIC_COLORS.success.text)}>
            <CheckCircle2Icon className="mt-0.5 h-4 w-4 shrink-0" />
            <span>파일의 계좌번호와 일치하는 계좌를 자동으로 찾았어요.</span>
          </div>
        )}
        {hasAccounts && matchState === "unmatched" && (
          <div className={cn("flex items-start gap-2 rounded-lg border px-3 py-2 text-xs", SEMANTIC_COLORS.warning.bgSoft, SEMANTIC_COLORS.warning.borderSoft, SEMANTIC_COLORS.warning.text)}>
            <AlertCircleIcon className="mt-0.5 h-4 w-4 shrink-0" />
            <span>파일의 계좌번호와 일치하는 계좌가 없어요. 계좌를 선택하거나 새로 추가하세요.</span>
          </div>
        )}
        {hasAccounts && matchState === "no-hint" && (
          <div className="flex items-start gap-2 rounded-lg border bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
            <InfoIcon className="mt-0.5 h-4 w-4 shrink-0" />
            <span>파일에서 계좌번호를 찾지 못했어요. 등록할 계좌를 선택하세요.</span>
          </div>
        )}
        {hintMismatch && (
          <div className={cn("flex items-start gap-2 rounded-lg border px-3 py-2 text-xs", SEMANTIC_COLORS.warning.bgSoft, SEMANTIC_COLORS.warning.borderSoft, SEMANTIC_COLORS.warning.text)}>
            <AlertCircleIcon className="mt-0.5 h-4 w-4 shrink-0" />
            <span>선택한 계좌의 계좌번호가 파일과 달라요. 다른 계좌의 거래가 섞일 수 있으니 계좌를 확인하세요.</span>
          </div>
        )}

        <div className="flex flex-col gap-2">
          {accounts.map((acc) => {
            const selected = acc.id === selectedId;
            return (
              <button
                key={acc.id}
                type="button"
                onClick={() => onSelect(acc.id)}
                className={cn(
                  "flex items-center gap-3 rounded-lg border p-3 text-left transition-colors",
                  selected ? "border-primary bg-primary/5" : "hover:bg-accent",
                )}
              >
                <BrokerLogo broker={acc.broker} size={32} />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5">
                    <span className="truncate text-sm font-medium">{acc.name}</span>
                    {acc.id === matchedAccountId && (
                      <span className={cn("shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium", SEMANTIC_COLORS.success.bgSoft, SEMANTIC_COLORS.success.text)}>
                        자동 매칭
                      </span>
                    )}
                  </span>
                  {acc.account_number && (
                    <span className="block truncate text-xs tabular-nums text-muted-foreground">
                      {acc.account_number}
                    </span>
                  )}
                </span>
                {selected && <CheckIcon className="h-4 w-4 shrink-0 text-primary" />}
              </button>
            );
          })}

          {/* 신규 등록 카드 */}
          <button
            type="button"
            onClick={() => onSelect(NEW_ACCOUNT_ID)}
            className={cn(
              "flex items-center gap-3 rounded-lg border p-3 text-left transition-colors",
              selectedId === NEW_ACCOUNT_ID ? "border-primary bg-primary/5" : "hover:bg-accent",
            )}
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
              <PlusIcon className="h-4 w-4" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">새 계좌로 등록</span>
              <span className="block truncate text-xs text-muted-foreground">
                {computedAccountName || brokerLabel || "새 계좌를 만들어요"}
              </span>
            </span>
            {selectedId === NEW_ACCOUNT_ID && <CheckIcon className="h-4 w-4 shrink-0 text-primary" />}
          </button>
        </div>
      </div>

      <FullScreenPanelFooter>
        <div className="flex gap-2">
          <Button size="xl" variant="outline" type="button" onClick={onBack} disabled={isLoading}>
            이전
          </Button>
          <Button
            size="xl"
            className="flex-1"
            type="button"
            onClick={onNext}
            disabled={!selectedId || isLoading}
          >
            {isLoading ? "분석 중..." : "다음"}
          </Button>
        </div>
      </FullScreenPanelFooter>
    </div>
  );
}
