"use client";

import { useState } from "react";
import { ChevronDownIcon, ChevronUpIcon, AlertCircleIcon, InfoIcon } from "lucide-react";
import { Button } from "@/components/base/Button";
import { AccountChip } from "@/components/shared/AccountChip";
import { FullScreenPanelFooter } from "@/components/base/FullScreenPanel";
import type { ImportPreviewResponse } from "@/lib/api-client";
import type { Account } from "@/types/database";

// 해외(USD) 일괄 등록을 지원하는 broker_key. 그 외 브로커는 해외 행이 조용히
// 누락될 수 있어 미지원 고지를 유지한다.
const OVERSEAS_SUPPORTED_BROKERS = new Set(["toss_pdf"]);

interface Props {
  preview: ImportPreviewResponse;
  /** 계좌 선택 스텝에서 확정한 기존 등록 대상 계좌. 신규 등록이면 null 이고 newAccountName 을 쓴다. */
  resolvedAccount: Account | null;
  /** 신규 계좌로 등록 시 표시할 계좌명(commit 시 자동 생성). 기존 계좌면 null. */
  newAccountName?: string | null;
  /** 선택 계좌가 파일 계좌번호와 어긋남 — mis-route 경고용(주로 단일계좌 스킵 경로 잔여). */
  hintMismatch: boolean;
  /** 계좌 선택 스텝으로 돌아가 계좌를 바꾼다. */
  onChangeAccount: () => void;
  onCommit: () => void;
  onBack?: () => void;
  /** 해외 거래내역서 제보 진입. */
  onReportOverseas: () => void;
  isLoading: boolean;
}

function buildCommitLabel(newCount: number, dupCount: number, excludedCount: number): string {
  const parts: string[] = [];
  if (newCount > 0) parts.push(`${newCount}건 등록`);
  if (dupCount > 0) parts.push(`${dupCount}건 갱신`);
  if (parts.length === 0) return "등록하기";
  const prefix = excludedCount > 0 ? `제외하고 ` : "";
  return `${prefix}${parts.join(" · ")}하기`;
}

function CountCard({ label, value, variant = "default" }: {
  label: string;
  value: number;
  variant?: "default" | "success" | "warn" | "error";
}) {
  const color = {
    default: "text-foreground",
    success: "text-green-600 dark:text-green-400",
    warn: "text-yellow-600 dark:text-yellow-400",
    error: "text-red-600 dark:text-red-400",
  }[variant];

  return (
    <div className="flex flex-col items-center rounded-lg border bg-card p-4">
      <span className={`text-2xl font-bold ${color}`}>{value}</span>
      <span className="mt-1 text-center text-xs text-muted-foreground">{label}</span>
    </div>
  );
}

export function PreviewStep({
  preview,
  resolvedAccount,
  newAccountName,
  hintMismatch,
  onChangeAccount,
  onCommit,
  onBack,
  onReportOverseas,
  isLoading,
}: Props) {
  const [showErrors, setShowErrors] = useState(false);
  const hasErrors = preview.errors.length > 0;
  const validationErrors = preview.validation_errors ?? [];
  const hasValidationError = validationErrors.length > 0;
  const excludedCount = preview.excluded_count ?? 0;
  const foreignCount = preview.foreign_count ?? 0;
  const overseasUnsupported = !OVERSEAS_SUPPORTED_BROKERS.has(preview.broker_key);
  // 제외 예정 그룹은 보통 신규 등록으로 분류돼 있으므로 차감해서 실제 등록 예정 수를 표시한다.
  const effectiveNewCount = Math.max(0, preview.new_count - excludedCount);
  const totalExcluded = preview.error_count + excludedCount;

  return (
    <div className="flex flex-col min-h-full">
      <div className="flex-1 px-5 pt-2 pb-4 space-y-5">
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{preview.broker_name}</span> 거래내역서 분석 결과
        </p>

        <div className="grid grid-cols-3 gap-3">
          <CountCard label="신규 등록" value={effectiveNewCount} variant="success" />
          <CountCard label="기존 거래 갱신(근사)" value={preview.duplicate_count} variant="default" />
          <CountCard
            label="제외 예정"
            value={totalExcluded}
            variant={totalExcluded > 0 ? "warn" : "default"}
          />
        </div>

        {foreignCount > 0 ? (
          // 해외(USD) 거래가 감지·등록됨. 침묵 누락이 아니라 함께 등록됨을 안내한다.
          <div className="rounded-lg border bg-muted/50 px-4 py-3 text-sm text-muted-foreground">
            <div className="flex items-start gap-2">
              <InfoIcon className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                해외 거래 {foreignCount}건 포함됨(USD) — 외화 기준으로 함께 등록됩니다.
              </span>
            </div>
          </div>
        ) : overseasUnsupported ? (
          // 해외 미지원 브로커는 해외 행이 조용히 누락(silent loss)될 수 있어
          // 감지 여부와 무관하게 고지하고 제보 경로를 제공한다.
          <div className="rounded-lg border bg-muted/50 px-4 py-3 text-sm text-muted-foreground">
            <div className="flex items-start gap-2">
              <InfoIcon className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                해외(미국 등) 거래는 아직 일괄 등록을 지원하지 않습니다. 이 결과에는 국내 거래만
                포함되어 있으니, 해외 거래가 있다면 직접 입력해 주세요.
              </span>
            </div>
            <button
              type="button"
              onClick={onReportOverseas}
              className="mt-2 w-full rounded-md border border-primary/40 py-2 text-xs font-medium text-primary transition-colors hover:bg-primary/5"
            >
              해외 거래내역서 제보
            </button>
          </div>
        ) : null}
        {preview.duplicate_count > 0 && (
          <div className="flex items-start gap-2 rounded-lg border bg-muted/50 px-4 py-3 text-sm text-muted-foreground">
            <InfoIcon className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              같은 계좌·날짜·종목·단가·수량의 기존 거래는 수수료·세금·체결 시각만 갱신되고
              메모/감정/근거 등은 그대로 보존됩니다. 미리보기 카운트는 근사값이며 실제
              등록 시 정확히 처리됩니다.
            </span>
          </div>
        )}

        {preview.unresolved_ticker_count > 0 && (
          <div className="rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800 dark:border-yellow-800 dark:bg-yellow-950 dark:text-yellow-200">
            종목코드 미해결: {preview.unresolved_ticker_count}건 — 해당 종목은 등록되지 않습니다.
            종목명을 정확히 입력했는지 확인하거나, 거래내역의 종목명 표기를 점검해주세요.
          </div>
        )}

        {hasValidationError && (
          <div className="rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800 dark:border-yellow-800 dark:bg-yellow-950 dark:text-yellow-200">
            <div className="flex items-start gap-2">
              <AlertCircleIcon className="mt-0.5 h-4 w-4 shrink-0" />
              <div className="flex-1 space-y-1.5">
                <p className="font-medium">
                  일부 거래가 제외됩니다{excludedCount > 0 ? ` (${excludedCount}건)` : ""}
                </p>
                <ul className="list-disc space-y-1 pl-5 text-xs">
                  {validationErrors.map((e, i) => (
                    <li key={i}>{e.reason}</li>
                  ))}
                </ul>
                <p className="text-xs">아래 종목 거래는 제외되고 나머지 거래만 등록됩니다.</p>
              </div>
            </div>
          </div>
        )}

        {/* 등록 대상 계좌 — 계좌 선택 스텝에서 확정, 여기서는 읽기전용 표시 + 변경 링크 */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">등록 대상 계좌</p>
            <button
              type="button"
              onClick={onChangeAccount}
              disabled={isLoading}
              className="text-[13px] font-medium text-primary disabled:opacity-50"
            >
              계좌 변경
            </button>
          </div>

          {hintMismatch && (
            <div className="flex items-start gap-2 rounded-lg border border-yellow-200 bg-yellow-50 px-3 py-2 text-xs text-yellow-800 dark:border-yellow-800 dark:bg-yellow-950 dark:text-yellow-200">
              <AlertCircleIcon className="mt-0.5 h-4 w-4 shrink-0" />
              <span>선택한 계좌의 계좌번호가 파일과 달라요. 다른 계좌의 거래가 섞일 수 있으니 계좌를 확인하세요.</span>
            </div>
          )}

          <div className="flex items-center gap-3 rounded-2xl border bg-card p-4">
            {resolvedAccount ? (
              <div className="flex min-w-0 flex-1 items-center justify-between gap-2">
                <AccountChip account={resolvedAccount} size="md" className="overflow-hidden" />
                {resolvedAccount.account_number && (
                  <span className="shrink-0 truncate text-xs tabular-nums text-muted-foreground">
                    {resolvedAccount.account_number}
                  </span>
                )}
              </div>
            ) : newAccountName ? (
              // 신규 계좌 — 등록 시(commit) 자동 생성. 별도 계좌 등록 페이지 없이 여기서 확인만.
              <div className="flex min-w-0 flex-1 items-center justify-between gap-2">
                <span className="min-w-0 truncate text-sm font-medium">
                  <span className="text-primary">새 계좌</span> {newAccountName}
                </span>
                {preview.account_hint && (
                  <span className="shrink-0 truncate text-xs tabular-nums text-muted-foreground">
                    {preview.account_hint}
                  </span>
                )}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">계좌를 선택하세요</p>
            )}
          </div>
        </div>

        {hasErrors && (
          <div>
            <button
              type="button"
              className="flex w-full items-center justify-between rounded-lg border px-4 py-2 text-sm"
              onClick={() => setShowErrors((v) => !v)}
            >
              <span>제외된 행 상세 ({preview.errors.length}건)</span>
              {showErrors ? <ChevronUpIcon className="h-4 w-4" /> : <ChevronDownIcon className="h-4 w-4" />}
            </button>
            {showErrors && (
              <ul className="mt-2 max-h-40 overflow-y-auto rounded-lg border bg-muted/30 p-2 text-xs text-muted-foreground space-y-1">
                {preview.errors.map((e, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="shrink-0 font-mono">행 {e.row_no}</span>
                    <span>{e.reason}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <FullScreenPanelFooter>
        <div className="flex gap-2">
          {onBack && (
            <Button
              size="xl"
              variant="outline"
              type="button"
              onClick={onBack}
              disabled={isLoading}
            >
              이전
            </Button>
          )}
          <Button
            size="xl"
            className="flex-1"
            onClick={onCommit}
            disabled={
              (!resolvedAccount && !newAccountName)
              || (effectiveNewCount === 0 && preview.duplicate_count === 0)
              || isLoading
            }
          >
            {isLoading
              ? "등록 중..."
              : buildCommitLabel(effectiveNewCount, preview.duplicate_count, excludedCount)}
          </Button>
        </div>
      </FullScreenPanelFooter>
    </div>
  );
}
