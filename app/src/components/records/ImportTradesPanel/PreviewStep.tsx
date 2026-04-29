"use client";

import { useState } from "react";
import { ChevronDownIcon, ChevronUpIcon, AlertCircleIcon } from "lucide-react";
import { Button } from "@/components/base/Button";
import { BrokerLogo } from "@/components/base/BrokerLogo";
import type { ImportPreviewResponse } from "@/lib/api-client";
import type { Account } from "@/types/database";

interface Props {
  preview: ImportPreviewResponse;
  account: Account;
  onCommit: () => void;
  isLoading: boolean;
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
      <span className="mt-1 text-xs text-muted-foreground">{label}</span>
    </div>
  );
}

export function PreviewStep({ preview, account, onCommit, isLoading }: Props) {
  const [showErrors, setShowErrors] = useState(false);
  const hasErrors = preview.errors.length > 0;
  const hint = preview.account_hint;
  const hintMismatch = !!hint && !account.name?.includes(hint);

  return (
    <div className="flex flex-col min-h-full">
      <div className="flex-1 px-5 pt-2 pb-4 space-y-5">
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{preview.broker_name}</span> 거래내역서 분석 결과
        </p>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <CountCard label="신규 등록" value={preview.new_count} variant="success" />
          <CountCard label="중복(근사)" value={preview.duplicate_count} variant="default" />
          <CountCard label="제외된 오류" value={preview.error_count} variant={preview.error_count > 0 ? "warn" : "default"} />
          <CountCard label="USD 미지원" value={preview.usd_skip_count} variant={preview.usd_skip_count > 0 ? "warn" : "default"} />
        </div>
        {preview.duplicate_count > 0 && (
          <p className="text-xs text-muted-foreground -mt-3">
            * 미리보기 단계의 근사값이며, 실제 등록 시 정확히 처리됩니다.
          </p>
        )}

        {preview.unresolved_ticker_count > 0 && (
          <div className="rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800 dark:border-yellow-800 dark:bg-yellow-950 dark:text-yellow-200">
            종목코드 미해결: {preview.unresolved_ticker_count}건 — 해당 종목은 등록되지 않습니다.
            종목명을 정확히 입력했는지 확인하거나, 거래내역의 종목명 표기를 점검해주세요.
          </div>
        )}

        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium">등록 대상 계좌</p>
          <div className="flex items-center gap-3 rounded-2xl bg-muted/60 p-4">
            <BrokerLogo broker={account.broker} size={32} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{account.name}</p>
              {account.broker && (
                <p className="truncate text-xs text-muted-foreground">{account.broker}</p>
              )}
            </div>
          </div>
          {hintMismatch && (
            <div className="flex items-start gap-2 rounded-lg border border-yellow-200 bg-yellow-50 px-3 py-2 text-xs text-yellow-800 dark:border-yellow-800 dark:bg-yellow-950 dark:text-yellow-200">
              <AlertCircleIcon className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                파일의 계좌번호({hint})와 선택한 계좌가 다를 수 있습니다. 그대로 등록하려면 계속 진행하세요.
              </span>
            </div>
          )}
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

      <div
        className="sticky bottom-0 bg-background px-5 pt-3 pb-4"
        style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }}
      >
        <Button
          size="xl"
          className="w-full"
          onClick={onCommit}
          disabled={preview.new_count === 0 || isLoading}
        >
          {isLoading ? "등록 중..." : `${preview.new_count}건 등록하기`}
        </Button>
      </div>
    </div>
  );
}
