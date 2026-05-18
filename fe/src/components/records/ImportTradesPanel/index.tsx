"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  FullScreenPanelHeader,
  FullScreenPanelBody,
} from "@/components/base/FullScreenPanel";
import { queryKeys } from "@/lib/query-keys";
import { importApi, type ImportPreviewResponse, type ImportCommitResponse } from "@/lib/api-client";
import { ApiError } from "@/lib/api-client";
import { AccountStep } from "./AccountStep";
import { FileStep } from "./FileStep";
import { PreviewStep } from "./PreviewStep";
import { ResultStep } from "./ResultStep";
import { BROKER_OPTIONS, findBrokerKeyByAccountBroker } from "./brokers";
import type { Account } from "@/types/database";

type Step = "account" | "file" | "preview" | "result";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  accounts: Account[];
}

// 마운트 시점에 일괄 등록 가능한 계좌가 정확히 1개면 default select.
// effect-setState 안티패턴 회피를 위해 부모 lazy initializer 로 한 번만 결정.
export function getInitialSelectedAccountId(accounts: Account[]): string {
  const eligible = accounts.filter(
    (a) => findBrokerKeyByAccountBroker(a.broker) !== null,
  );
  return eligible.length === 1 ? eligible[0].id : "";
}

export function ImportTradesPanel({ open, onOpenChange, accounts }: Props) {
  const queryClient = useQueryClient();
  const [step, setStep] = useState<Step>("account");
  const [selectedAccountId, setSelectedAccountId] = useState<string>(
    () => getInitialSelectedAccountId(accounts),
  );
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [result, setResult] = useState<ImportCommitResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const selectedAccount = accounts.find((a) => a.id === selectedAccountId) ?? null;
  const effectiveBrokerKey = findBrokerKeyByAccountBroker(selectedAccount?.broker);
  const effectiveBroker = BROKER_OPTIONS.find((b) => b.key === effectiveBrokerKey);

  // reset 은 부모(TradeList) 가 importKey 를 ++ 해 새 인스턴스를 마운트하는 방식으로 처리.
  // 닫힘 애니메이션 중 step 깜박임 방지(이전 setTimeout 의 의도)는, 닫는 동안 같은 인스턴스가
  // 자기 state 를 유지한 채 슬라이드 아웃하는 lifecycle 로 자연 보존된다.

  const handleFileSelect = async (file: File) => {
    if (!effectiveBrokerKey) return;
    setIsLoading(true);
    try {
      const res = await importApi.preview(file, effectiveBrokerKey, selectedAccountId);
      setPreview(res);
      setStep("preview");
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "파일 분석 중 오류가 발생했습니다.";
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCommit = async () => {
    if (!preview || !selectedAccountId) return;
    setIsLoading(true);
    try {
      const res = await importApi.commit(preview.staging_id, selectedAccountId);
      setResult(res);
      setStep("result");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.trades }),
        queryClient.invalidateQueries({ queryKey: queryKeys.portfolioSummary }),
      ]);
      if (res.inserted_count > 0 || res.merged_count > 0) {
        const parts: string[] = [];
        if (res.inserted_count > 0) parts.push(`${res.inserted_count}건 신규 등록`);
        if (res.merged_count > 0) parts.push(`${res.merged_count}건 갱신`);
        toast.success(parts.join(" · "));
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "등록 중 오류가 발생했습니다.";
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    onOpenChange(false);
  };

  return (
    <FullScreenPanel open={open} onOpenChange={onOpenChange}>
      <FullScreenPanelContent>
        <FullScreenPanelHeader title="거래 일괄 등록" />
        <FullScreenPanelBody>
          {step === "account" && (
            <AccountStep
              accounts={accounts}
              selectedAccountId={selectedAccountId}
              onSelect={setSelectedAccountId}
              onNext={() => setStep("file")}
            />
          )}
          {step === "file" && (
            <FileStep
              brokerName={effectiveBroker?.label ?? "증권사"}
              accept={effectiveBroker?.accept ?? ".xlsx,.xls,.pdf"}
              downloadGuide={effectiveBroker?.downloadGuide}
              onFileSelect={handleFileSelect}
              onBack={() => setStep("account")}
              isLoading={isLoading}
            />
          )}
          {step === "preview" && preview && selectedAccount && (
            <PreviewStep
              preview={preview}
              account={selectedAccount}
              onCommit={handleCommit}
              onBack={() => {
                setPreview(null);
                setStep("file");
              }}
              isLoading={isLoading}
            />
          )}
          {step === "result" && result && (
            <ResultStep result={result} onClose={handleClose} />
          )}
        </FullScreenPanelBody>
      </FullScreenPanelContent>
    </FullScreenPanel>
  );
}
