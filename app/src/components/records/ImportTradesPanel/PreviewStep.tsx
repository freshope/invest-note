"use client";

import { useState } from "react";
import { ChevronDownIcon, ChevronUpIcon } from "lucide-react";
import { Button } from "@/components/base/Button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/base/Select";
import type { ImportPreviewResponse } from "@/lib/api-client";
import type { Account } from "@/types/database";

interface Props {
  preview: ImportPreviewResponse;
  accounts: Account[];
  selectedAccountId: string;
  onAccountChange: (id: string) => void;
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

export function PreviewStep({
  preview,
  accounts,
  selectedAccountId,
  onAccountChange,
  onCommit,
  isLoading,
}: Props) {
  const [showErrors, setShowErrors] = useState(false);
  const hasErrors = preview.errors.length > 0;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{preview.broker_name}</span> 거래내역서 분석 결과
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <CountCard label="신규 등록" value={preview.new_count} variant="success" />
        <CountCard label="중복(근사)" value={preview.duplicate_count} variant="default" />
        <CountCard label="제외된 오류" value={preview.error_count} variant={preview.error_count > 0 ? "warn" : "default"} />
        <CountCard label="USD 미지원" value={preview.usd_skip_count} variant={preview.usd_skip_count > 0 ? "warn" : "default"} />
      </div>
      {preview.duplicate_count > 0 && (
        <p className="text-xs text-muted-foreground -mt-3">
          * 중복 건수는 계좌 선택 전 근사값이며, 실제 등록 시 정확히 처리됩니다.
        </p>
      )}

      {preview.unresolved_ticker_count > 0 && (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3 text-sm text-yellow-800 dark:border-yellow-800 dark:bg-yellow-950 dark:text-yellow-200">
          종목코드 미해결: {preview.unresolved_ticker_count}건 — 해당 종목은 등록되지 않습니다.
          종목명을 정확히 입력했는지 확인하거나, 거래내역의 종목명 표기를 점검해주세요.
        </div>
      )}

      <div className="flex flex-col gap-2">
        <label className="text-sm font-medium">계좌 선택</label>
        <Select value={selectedAccountId} onValueChange={onAccountChange}>
          <SelectTrigger className="w-full">
            <SelectValue placeholder="거래를 등록할 계좌를 선택하세요" />
          </SelectTrigger>
          <SelectContent>
            {accounts.map((a) => (
              <SelectItem key={a.id} value={a.id}>
                {a.name} {a.broker ? `(${a.broker})` : ""}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {preview.account_hint && (
          <p className="text-xs text-muted-foreground">
            파일 계좌번호: {preview.account_hint}
          </p>
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

      <Button
        onClick={onCommit}
        disabled={!selectedAccountId || preview.new_count === 0 || isLoading}
        className="self-end"
      >
        {isLoading ? "등록 중..." : `${preview.new_count}건 등록하기`}
      </Button>
    </div>
  );
}
