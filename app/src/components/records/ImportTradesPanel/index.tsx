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
import { BrokerStep } from "./BrokerStep";
import { FileStep } from "./FileStep";
import { PreviewStep } from "./PreviewStep";
import { ResultStep } from "./ResultStep";
import type { Account } from "@/types/database";

type Step = "broker" | "file" | "preview" | "result";

const BROKER_NAMES: Record<string, string> = {
  samsung_xlsx: "삼성증권",
  toss_pdf: "토스증권",
};

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  accounts: Account[];
}

export function ImportTradesPanel({ open, onOpenChange, accounts }: Props) {
  const queryClient = useQueryClient();
  const [step, setStep] = useState<Step>("broker");
  const [detectedBrokerKey, setDetectedBrokerKey] = useState<string | null>(null);
  const [selectedBrokerKey, setSelectedBrokerKey] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [result, setResult] = useState<ImportCommitResponse | null>(null);
  const [selectedAccountId, setSelectedAccountId] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);

  const effectiveBrokerKey = selectedBrokerKey ?? detectedBrokerKey;

  const handleFileSelect = async (file: File) => {
    setSelectedFile(file);
    setIsLoading(true);
    try {
      const res = await importApi.preview(file, effectiveBrokerKey ?? undefined);
      setDetectedBrokerKey(res.broker_key);
      setPreview(res);

      // 계좌 자동 매칭 시도 (account_hint vs accounts 이름/브로커)
      if (accounts.length === 1) {
        setSelectedAccountId(accounts[0].id);
      } else if (res.account_hint) {
        const matched = accounts.find(
          (a) => a.name?.includes(res.account_hint!) || res.account_hint?.includes(a.name ?? "")
        );
        if (matched) setSelectedAccountId(matched.id);
      }
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
      await queryClient.invalidateQueries({ queryKey: queryKeys.trades });
      if (res.inserted_count > 0) {
        toast.success(`${res.inserted_count}건의 거래가 등록되었습니다.`);
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
    // 닫힌 후 상태 초기화
    setTimeout(() => {
      setStep("broker");
      setDetectedBrokerKey(null);
      setSelectedBrokerKey(null);
      setSelectedFile(null);
      setPreview(null);
      setResult(null);
      setSelectedAccountId("");
    }, 300);
  };

  const stepTitle: Record<Step, string> = {
    broker: "증권사 선택",
    file: "파일 선택",
    preview: "등록 미리보기",
    result: "등록 결과",
  };

  return (
    <FullScreenPanel open={open} onOpenChange={onOpenChange}>
      <FullScreenPanelContent>
        <FullScreenPanelHeader title={`거래 일괄 등록 — ${stepTitle[step]}`} />
        <FullScreenPanelBody>
          {step === "broker" && (
            <BrokerStep
              detectedBrokerKey={detectedBrokerKey}
              selectedBrokerKey={selectedBrokerKey}
              onSelect={setSelectedBrokerKey}
              onNext={() => setStep("file")}
            />
          )}
          {step === "file" && (
            <FileStep
              brokerName={BROKER_NAMES[effectiveBrokerKey ?? ""] ?? "증권사"}
              onFileSelect={handleFileSelect}
              isLoading={isLoading}
            />
          )}
          {step === "preview" && preview && (
            <PreviewStep
              preview={preview}
              accounts={accounts}
              selectedAccountId={selectedAccountId}
              onAccountChange={setSelectedAccountId}
              onCommit={handleCommit}
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
