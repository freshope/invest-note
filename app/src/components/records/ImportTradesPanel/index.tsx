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
import {
  importApi,
  accountsApi,
  type ImportPreviewResponse,
  type ImportCommitResponse,
} from "@/lib/api-client";
import { ApiError } from "@/lib/api-client";
import { AccountStep } from "./AccountStep";
import { AccountSelectStep, NEW_ACCOUNT_ID } from "./AccountSelectStep";
import { FileStep } from "./FileStep";
import { PreviewStep } from "./PreviewStep";
import { ResultStep } from "./ResultStep";
import { BROKER_OPTIONS, type BrokerKey } from "./brokers";
import { findAccountByHint, normalizeAccountNumber } from "@/lib/account";
import { capture } from "@/lib/analytics";
import {
  BrokerStatementPanel,
  type BrokerSource,
} from "@/components/broker-statement/BrokerStatementPanel";
import type { BrokerStatementType } from "@/lib/api-client";
import type { Account } from "@/types/database";

// broker → file → account(카드) → preview → commit(result). 계좌 선택은 account_hint 를
// 계좌번호로 매칭해 기본 카드를 제안하고, 사용자가 최종 확정한다.
type Step = "broker" | "file" | "account" | "preview" | "result";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  accounts: Account[];
}

export function ImportTradesPanel({ open, onOpenChange, accounts }: Props) {
  const queryClient = useQueryClient();
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
  // account 스텝에서 강조된 카드(계좌 id 또는 NEW_ACCOUNT_ID).
  const [accountStepSelection, setAccountStepSelection] = useState<string>("");
  // 확정된 등록 대상 계좌(기존 계좌 선택 시). 신규 등록은 pickedNew 로 표시하고 commit 시 생성한다.
  const [pickedAccount, setPickedAccount] = useState<Account | null>(null);
  // 신규 계좌로 등록 확정 여부 — 폼 없이 commit 시점에 자동 생성한다(계좌 등록 페이지 미방문).
  const [pickedNew, setPickedNew] = useState(false);
  // 거래내역서 제보 패널(dual-entry: 미지원 broker + 해외거래). null=닫힘.
  const [reportPayload, setReportPayload] = useState<{
    type: BrokerStatementType;
    brokerSource: BrokerSource;
  } | null>(null);

  const effectiveBroker = BROKER_OPTIONS.find((b) => b.key === selectedBrokerKey);
  const brokerLabel = effectiveBroker?.label ?? "";

  // ── 계좌번호 매칭 ──────────────────────────────────────────────
  const normalizedHint = normalizeAccountNumber(preview?.account_hint);
  const matchedAccount = findAccountByHint(accounts, preview?.account_hint);

  // 신규계좌 기본 계좌명: hint 있으면 "{증권사명}-{계좌번호 뒷4자리}", 없으면 증권사명.
  // (거래내역서에 별도 계좌 표시명이 없어 fallback 포맷만 사용 — 파서는 계좌번호만 추출.)
  const computedAccountName = normalizedHint
    ? `${brokerLabel}-${normalizedHint.slice(-4)}`
    : brokerLabel;

  // preview 스텝의 잔여 mismatch 경고(주로 단일계좌 스킵 경로 — account 스텝을 안 거쳐 확정된 계좌가
  // 파일 계좌번호와 다를 때). 다계좌는 account 스텝에서 이미 경고가 뜬다.
  const pickedNumber = normalizeAccountNumber(pickedAccount?.account_number);
  const hintMismatch = !!normalizedHint && !!pickedNumber && pickedNumber !== normalizedHint;

  // reset 은 부모(TradeList) 가 importKey 를 ++ 해 새 인스턴스를 마운트하는 방식으로 처리.

  const handleFileSelect = async (file: File) => {
    if (!selectedBrokerKey) return;
    setIsLoading(true);
    try {
      setSelectedFile(file);
      // 계좌가 1개뿐이면 계좌번호 매칭이 불필요 — account 스텝을 건너뛰고 그 계좌로 바로 scoped preview.
      // (마이그레이션 전 account_number=null 계좌라도 매칭 실패로 중복 신규계좌를 만드는 회귀를 방지.)
      if (accounts.length === 1) {
        const only = accounts[0];
        const scoped = await importApi.preview(file, selectedBrokerKey, only.id);
        setPreview(scoped);
        setPickedAccount(only);
        setPickedNew(false);
        setAccountStepSelection(only.id);
        setValidatedAccountId(only.id);
        setStep("preview");
        return;
      }
      // 다계좌(또는 0계좌): 1차 preview(account 없이)로 account_hint 확보 후 account 스텝에서 매칭 제안.
      const res = await importApi.preview(file, selectedBrokerKey);
      setPreview(res);
      const matched = findAccountByHint(accounts, res.account_hint);
      setAccountStepSelection(matched ? matched.id : NEW_ACCOUNT_ID);
      setValidatedAccountId("");
      setStep("account");
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "파일 분석 중 오류가 발생했습니다.";
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  };

  // account 스텝 "다음" — 신규 카드면 폼 없이 preview 로 직행(계좌는 commit 시 자동 생성),
  // 기존 계좌면 그 계좌 기준 재-preview 후 preview 스텝으로.
  const handleConfirmAccount = async () => {
    const sel = accountStepSelection;
    if (!sel) return;
    if (sel === NEW_ACCOUNT_ID) {
      // 신규 계좌는 commit 시 빈 계좌로 생성된다. account 없는 preview 가 BE 에서 이미 빈-보유
      // 가정의 oversell(무보유 매도·시점초과)을 계산해 두므로, 그 preview 그대로 진행하면
      // commit(빈 계좌 적용) 결과와 제외 집합이 일치한다(재-preview 불필요).
      setPickedNew(true);
      setPickedAccount(null);
      setStep("preview");
      return;
    }
    const acc = accounts.find((a) => a.id === sel);
    if (!acc) return;
    setPickedNew(false);
    // 아직 그 계좌 기준으로 검증(scoped preview)하지 않았으면 재-preview 해 oversell/카운트를 갱신한다.
    if (sel !== validatedAccountId && selectedFile && selectedBrokerKey) {
      setIsLoading(true);
      try {
        const scoped = await importApi.preview(selectedFile, selectedBrokerKey, sel);
        setPreview(scoped);
        setValidatedAccountId(sel);
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : "파일 분석 중 오류가 발생했습니다.";
        toast.error(msg);
        setIsLoading(false);
        return;
      }
      setIsLoading(false);
    }
    setPickedAccount(acc);
    setStep("preview");
  };

  // ★hint→account_number 자동기입 게이트(데이터 오염 방지) — commit 확정 직전에만 수행.
  // 조건: picked 기존 계좌의 계좌번호가 null/빈 값일 때만 write. 다른 번호가 있으면 write 금지(경고만).
  // 신규 생성 계좌는 이미 account_number=hint 로 만들어져 있어(번호 존재) 이 게이트를 통과하지 않는다.
  const maybeWriteHint = async (account: Account) => {
    const hint = preview?.account_hint;
    if (!normalizeAccountNumber(hint)) return;
    if (normalizeAccountNumber(account.account_number)) return; // 이미 번호 있음 → write 금지
    try {
      await accountsApi.update(account.id, { name: account.name, account_number: hint });
      await queryClient.invalidateQueries({ queryKey: queryKeys.accounts });
      toast.success("이 계좌에 계좌번호를 저장했어요. 다음부터 자동으로 매칭돼요.");
    } catch {
      // 자동기입 실패는 등록 자체를 막지 않는다(부가 편의 기능).
    }
  };

  // 실제 commit — 자체 try/catch(toast)로 밖으로 던지지 않는다.
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
    if (pickedNew) {
      // 신규 계좌는 계좌 등록 페이지 없이 commit 시점에 자동 생성한다.
      // 이름=거래내역서 표시명(없음)→"{증권사}-{뒷4자리}" fallback, 번호=파일 계좌번호.
      setIsLoading(true);
      let created: Account;
      try {
        created = await accountsApi.create({
          name: computedAccountName || brokerLabel || "새 계좌",
          broker: brokerLabel || null,
          account_number: preview.account_hint ?? null,
        });
        await queryClient.invalidateQueries({ queryKey: queryKeys.accounts });
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : "계좌 생성 중 오류가 발생했습니다.";
        toast.error(msg);
        setIsLoading(false);
        return;
      }
      setIsLoading(false);
      await commitTo(created.id);
      return;
    }
    if (!pickedAccount) return;
    await maybeWriteHint(pickedAccount);
    await commitTo(pickedAccount.id);
  };

  // preview → account 로 돌아가 계좌를 다시 고른다(단일계좌 스킵 경로도 여기서 변경 가능).
  const goToAccountStep = () => {
    setAccountStepSelection(
      pickedNew ? NEW_ACCOUNT_ID : (pickedAccount?.id ?? matchedAccount?.id ?? NEW_ACCOUNT_ID),
    );
    setStep("account");
  };

  // account → file 로 돌아가면 파일/preview 상태를 비워 재선택 시 새로 파싱한다.
  const backToFile = () => {
    setPreview(null);
    setSelectedFile(null);
    setValidatedAccountId("");
    setAccountStepSelection("");
    setPickedAccount(null);
    setPickedNew(false);
    setStep("file");
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
          {step === "account" && (
            <AccountSelectStep
              accounts={accounts}
              selectedId={accountStepSelection}
              onSelect={setAccountStepSelection}
              matchedAccountId={matchedAccount?.id ?? null}
              accountHint={preview?.account_hint ?? null}
              computedAccountName={computedAccountName}
              brokerLabel={brokerLabel}
              onNext={handleConfirmAccount}
              onBack={backToFile}
              isLoading={isLoading}
            />
          )}
          {step === "preview" && preview && (
            <PreviewStep
              preview={preview}
              resolvedAccount={pickedAccount}
              newAccountName={pickedNew ? computedAccountName : null}
              hintMismatch={hintMismatch}
              onChangeAccount={goToAccountStep}
              onCommit={handleCommit}
              onBack={goToAccountStep}
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
