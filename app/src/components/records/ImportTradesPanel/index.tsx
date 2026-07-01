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
import { BROKER_OPTIONS, type BrokerKey } from "./brokers";
import { AccountFormPanel } from "@/components/settings/AccountFormPanel";
import { findAccountByHint, normalizeAccountNumber } from "@/lib/account";
import { capture } from "@/lib/analytics";
import {
  BrokerStatementPanel,
  type BrokerSource,
} from "@/components/broker-statement/BrokerStatementPanel";
import type { BrokerStatementType } from "@/lib/api-client";
import type { Account } from "@/types/database";

type Step = "broker" | "file" | "preview" | "result";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  accounts: Account[];
}

export function ImportTradesPanel({ open, onOpenChange, accounts }: Props) {
  const queryClient = useQueryClient();
  // broker-first 흐름: 파서(broker)를 먼저 고르고, preview 의 account_hint 를 계좌번호로 매칭한다.
  // 계좌번호로 매칭하므로 다계좌에서도 안전(broker-only auto-select 의 silent mis-route 회피).
  const [step, setStep] = useState<Step>("broker");
  const [selectedBrokerKey, setSelectedBrokerKey] = useState<BrokerKey | null>(null);
  // 선택 파일 보관 — 계좌 확정 후 그 account_id 로 preview 를 재호출해 oversell 을 계산하려면
  // BE preview 가 파일 재전송을 요구하므로(파일 없이 staging_id 재검증 불가) 파일을 들고 있어야 한다.
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [result, setResult] = useState<ImportCommitResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  // 현재 preview 의 validation_errors 가 어느 계좌 기준인지("" = account 미지정 preview).
  const [validatedAccountId, setValidatedAccountId] = useState<string>("");
  // 자동매칭 결과를 사용자가 바꾸거나(override), 힌트 없음/불일치 시 직접 고르는 계좌.
  const [manualAccountId, setManualAccountId] = useState<string>("");
  // 신규계좌 확인 스텝(AccountFormPanel prefill).
  const [accountPanelOpen, setAccountPanelOpen] = useState(false);
  // 거래내역서 제보 패널(dual-entry: 미지원 broker + 해외거래). null=닫힘.
  const [reportPayload, setReportPayload] = useState<{
    type: BrokerStatementType;
    brokerSource: BrokerSource;
  } | null>(null);

  const effectiveBroker = BROKER_OPTIONS.find((b) => b.key === selectedBrokerKey);
  const brokerLabel = effectiveBroker?.label ?? "";

  // ── 계좌번호 매칭 ──────────────────────────────────────────────
  // 양쪽 정규화(숫자만) 후 전체 동일성. ★empty 오탐 방지: hint 가 있고(비어있지 않고),
  // 계좌 번호도 비어있지 않을 때만 매칭(null-number 계좌에 조용히 붙는 regression 차단).
  const normalizedHint = normalizeAccountNumber(preview?.account_hint);
  const matchedAccount = findAccountByHint(accounts, preview?.account_hint);

  // 해석: 수동 선택(override) 우선, 없으면 자동매칭. 신규생성은 commit 시 처리.
  const resolvedAccountId = manualAccountId || matchedAccount?.id || "";

  // 신규계좌 기본 계좌명: hint 있으면 "{증권사} {정규화 뒤4자리}", 없으면 증권사명.
  const computedAccountName = normalizedHint
    ? `${brokerLabel} ${normalizedHint.slice(-4)}`
    : brokerLabel;

  // 매칭 상태(표시용): manual=사용자 선택 / matched=자동매칭 / unmatched=힌트 있으나 없음 / no-hint=힌트 없음.
  const matchState: "manual" | "matched" | "unmatched" | "no-hint" = manualAccountId
    ? "manual"
    : matchedAccount
      ? "matched"
      : normalizedHint
        ? "unmatched"
        : "no-hint";

  // reset 은 부모(TradeList) 가 importKey 를 ++ 해 새 인스턴스를 마운트하는 방식으로 처리.

  const handleFileSelect = async (file: File) => {
    if (!selectedBrokerKey) return;
    setIsLoading(true);
    try {
      // 1차 preview 는 account_id 없이 — 계좌는 응답 account_hint 매칭으로 결정한다.
      const res = await importApi.preview(file, selectedBrokerKey);
      setSelectedFile(file);
      const matched = findAccountByHint(accounts, res.account_hint);
      if (matched) {
        // 자동매칭된 계좌 기준으로 재-preview → oversell(validation_errors/excluded_count)·
        // 신규 카운트를 그 계좌 기준으로 정확히 채운다(account_id 없는 preview 는 상시 빈값).
        const rescoped = await importApi.preview(file, selectedBrokerKey, matched.id);
        setPreview(rescoped);
        setValidatedAccountId(matched.id);
      } else {
        setPreview(res);
        setValidatedAccountId("");
      }
      setStep("preview");
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "파일 분석 중 오류가 발생했습니다.";
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  };

  // 사용자가 계좌를 직접 고르면(수동 선택/자동매칭 override) 그 계좌 기준으로 재-preview 해
  // oversell 검증·카운트를 갱신한다(기존 계좌만 — 보유가 있어 oversell 가능).
  const handleSelectAccount = async (id: string) => {
    setManualAccountId(id);
    if (!selectedFile || !selectedBrokerKey || !id || id === validatedAccountId) return;
    setIsLoading(true);
    try {
      const rescoped = await importApi.preview(selectedFile, selectedBrokerKey, id);
      setPreview(rescoped);
      setValidatedAccountId(id);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "파일 분석 중 오류가 발생했습니다.";
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  };

  // 실제 commit — 자체 try/catch(toast)로 밖으로 던지지 않는다(onCreated 안에서 호출 시 계좌 폼 에러 오귀속 방지).
  const commitTo = async (accountId: string) => {
    if (!preview || !accountId) return;
    setIsLoading(true);
    try {
      const res = await importApi.commit(preview.staging_id, accountId);
      setResult(res);
      setStep("result");
      capture("trades_imported", {
        broker: selectedBrokerKey, // 증권사 식별 키 — 종목/금액 아님
        inserted_count: res.inserted_count,
        merged_count: res.merged_count,
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.trades }),
        queryClient.invalidateQueries({ queryKey: queryKeys.portfolio }),
        queryClient.invalidateQueries({ queryKey: queryKeys.assets }),
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

  const handleCommit = async () => {
    if (!preview) return;
    // 매칭/수동선택된 계좌가 있으면 바로 commit, 없으면 신규계좌 확인 스텝으로.
    if (resolvedAccountId) {
      await commitTo(resolvedAccountId);
      return;
    }
    setAccountPanelOpen(true);
  };

  // 신규계좌 확인 스텝에서 계좌 생성 완료 → 그 id 로 바로 commit.
  const handleNewAccountCreated = (account: Account) => {
    void commitTo(account.id);
  };

  const handleClose = () => {
    onOpenChange(false);
  };

  // 거래내역서 제보 패널 오픈(dual-entry 공통). brokerLabel null/빈 값이면 패널이 freetext 폴백.
  const openReport = (type: BrokerStatementType, label: string | null) =>
    setReportPayload({ type, brokerSource: { mode: "fixed", label: label ?? "" } });

  return (
    <FullScreenPanel open={open} onOpenChange={onOpenChange}>
      <FullScreenPanelContent>
        <FullScreenPanelHeader title="거래 일괄 등록" />
        <FullScreenPanelBody>
          {step === "broker" && (
            <AccountStep
              brokerKey={selectedBrokerKey}
              onSelectBroker={setSelectedBrokerKey}
              onNext={() => setStep("file")}
              onReportUnsupported={() => openReport("unsupported_broker", null)}
            />
          )}
          {step === "file" && (
            <FileStep
              brokerName={brokerLabel || "증권사"}
              accept={effectiveBroker?.accept ?? ".xlsx,.xls,.pdf"}
              downloadGuide={effectiveBroker?.downloadGuide}
              onFileSelect={handleFileSelect}
              onBack={() => setStep("broker")}
              isLoading={isLoading}
            />
          )}
          {step === "preview" && preview && (
            <PreviewStep
              preview={preview}
              accounts={accounts}
              matchState={matchState}
              resolvedAccountId={resolvedAccountId}
              computedAccountName={computedAccountName}
              onSelectAccount={handleSelectAccount}
              onAddNewAccount={() => setAccountPanelOpen(true)}
              onCommit={handleCommit}
              onBack={() => {
                setPreview(null);
                setManualAccountId("");
                setValidatedAccountId("");
                setStep("file");
              }}
              onReportOverseas={() => openReport("overseas_trade", brokerLabel || null)}
              isLoading={isLoading}
            />
          )}
          {step === "result" && result && (
            <ResultStep
              result={result}
              onClose={handleClose}
              onReportOverseas={
                brokerLabel
                  ? () => openReport("overseas_trade", brokerLabel)
                  : undefined
              }
            />
          )}
        </FullScreenPanelBody>
      </FullScreenPanelContent>

      {/* 신규계좌 확인 스텝 — broker/계좌번호/계좌명 prefill, 생성 즉시 그 계좌로 commit */}
      <AccountFormPanel
        open={accountPanelOpen}
        onOpenChange={setAccountPanelOpen}
        onCreated={handleNewAccountCreated}
        defaultName={computedAccountName}
        defaultBroker={brokerLabel || null}
        defaultAccountNumber={preview?.account_hint ?? ""}
        source="import"
      />

      {reportPayload && (
        <BrokerStatementPanel
          open
          onOpenChange={(o) => {
            if (!o) setReportPayload(null);
          }}
          defaultType={reportPayload.type}
          brokerSource={reportPayload.brokerSource}
        />
      )}
    </FullScreenPanel>
  );
}
