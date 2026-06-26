"use client";

import { useEffect, useRef, useState } from "react";
import { UploadCloudIcon, FileIcon } from "lucide-react";
import { toast } from "sonner";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  FullScreenPanelHeader,
  FullScreenPanelBody,
  FullScreenPanelFooter,
} from "@/components/base/FullScreenPanel";
import { Button } from "@/components/base/Button";
import { Checkbox } from "@/components/base/Checkbox";
import { Input } from "@/components/base/Input";
import { Label } from "@/components/base/Label";
import {
  brokerStatementApi,
  ApiError,
  type BrokerStatementType,
} from "@/lib/api-client";
import { BROKERS } from "@/lib/brokers";
import { capture } from "@/lib/analytics";

// 제보 시 증권사명을 어떻게 결정하는지. fixed=호출 맥락이 계좌 증권사를 알고 있어 라벨 고정,
// freetext=사용자가 직접 입력(설정 독립 진입).
export type BrokerSource =
  | { mode: "freetext" }
  | { mode: "fixed"; label: string };

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultType: BrokerStatementType;
  brokerSource: BrokerSource;
}

const ACCEPT = ".xlsx,.xls,.pdf";

// register 단계 게이트와 동일한 한도. presign 이전에 사용자에게 즉시 피드백.
const MAX_SIZE_BYTES = 20 * 1024 * 1024;

const TITLE: Record<BrokerStatementType, string> = {
  unsupported_broker: "거래내역서 제보",
  overseas_trade: "해외 거래내역서 제보",
};

// status 코드별 사용자 친화 메시지(BE 원문 대신 일관된 안내 문구로 분기).
function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    switch (err.status) {
      case 400:
        return "업로드가 완료되지 않았습니다. 다시 시도해주세요.";
      case 413:
        return "파일이 너무 큽니다. 20MB 이하로 업로드해주세요.";
      case 415:
        return "지원하지 않는 파일 형식입니다. 엑셀(.xlsx/.xls) 또는 PDF 파일을 올려주세요.";
      case 503:
        return "지금은 제보를 받을 수 없습니다. 잠시 후 다시 시도해주세요.";
      case 429:
        return "제보가 너무 잦습니다. 잠시 후 다시 시도해주세요.";
      case 403:
        return "권한이 없는 요청입니다. 다시 시도해주세요.";
    }
  }
  return "제보 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.";
}

export function BrokerStatementPanel({
  open,
  onOpenChange,
  defaultType,
  brokerSource,
}: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  // fixed 모드라도 라벨이 비어 있으면(예: 증권사 미설정 계좌, broker=null) freetext 로
  // 폴백해 사용자가 직접 입력하게 한다 — 빈 라벨 read-only 면 제출이 영구 불가해진다.
  const fixedLabel = brokerSource.mode === "fixed" ? brokerSource.label.trim() : "";
  const isFixedBroker = fixedLabel.length > 0;
  const [broker, setBroker] = useState(fixedLabel);
  const [consent, setConsent] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // 진입(open) 시마다 폼을 초기 상태로 — 패널 컴포넌트는 항상 마운트되어 있어
  // 직전 입력값이 useState 에 남기 때문. broker 는 fixed 라벨(없으면 빈 값)로 복원.
  useEffect(() => {
    if (open) {
      setBroker(fixedLabel);
      setConsent(false);
      setFile(null);
    }
  }, [open, fixedLabel]);

  const brokerValid = broker.trim().length > 0;
  const canSubmit = consent && brokerValid && !!file && !submitting;

  const handleFilePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = e.target.files?.[0] ?? null;
    if (picked && picked.size > MAX_SIZE_BYTES) {
      toast.error("파일이 너무 큽니다. 20MB 이하로 업로드해주세요.");
      e.target.value = "";
      return;
    }
    setFile(picked);
  };

  const handleSubmit = async () => {
    if (!file || !canSubmit) return;
    setSubmitting(true);
    try {
      // content_type 단일 소스 — presign·PUT·submit 세 곳에 동일하게 흘린다.
      const contentType = file.type || "application/octet-stream";
      const meta = {
        original_name: file.name,
        content_type: contentType,
        size_bytes: file.size,
      };

      const presigned = await brokerStatementApi.presign(meta);
      await brokerStatementApi.uploadToR2(presigned.upload_url, file, contentType);
      await brokerStatementApi.submit({
        type: defaultType,
        broker: broker.trim(),
        consent: true,
        attachment: { ...meta, storage_key: presigned.storage_key },
      });

      capture("broker_statement_submitted", { type: defaultType });
      toast.success("제보가 접수되었습니다. 감사합니다!");
      onOpenChange(false);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <FullScreenPanel open={open} onOpenChange={onOpenChange}>
      <FullScreenPanelContent>
        <FullScreenPanelHeader title={TITLE[defaultType]} />
        <FullScreenPanelBody>
          <div className="px-5 pt-2 pb-4 space-y-6">
            <p className="text-sm text-muted-foreground leading-relaxed">
              아직 지원하지 않는 증권사나 해외 거래가 포함된 거래내역서를 보내주시면,
              파싱 지원을 추가하는 데 활용합니다. 파일은 관리자만 확인합니다.
            </p>

            {/* 증권사 */}
            <div className="space-y-2">
              <Label htmlFor="bs-broker">증권사</Label>
              {isFixedBroker ? (
                <div className="flex h-12 items-center rounded-xl bg-muted px-4 text-[15px] font-medium">
                  {fixedLabel}
                </div>
              ) : (
                <>
                  <Input
                    id="bs-broker"
                    list="bs-broker-candidates"
                    placeholder="증권사명을 입력하세요"
                    value={broker}
                    onChange={(e) => setBroker(e.target.value)}
                    autoComplete="off"
                  />
                  <datalist id="bs-broker-candidates">
                    {BROKERS.map((b) => (
                      <option key={b.slug} value={b.name} />
                    ))}
                  </datalist>
                </>
              )}
            </div>

            {/* 파일 선택 */}
            <div className="space-y-2">
              <Label>거래내역서 파일</Label>
              <input
                ref={fileInputRef}
                type="file"
                accept={ACCEPT}
                className="hidden"
                onChange={handleFilePick}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="flex w-full items-center gap-3 rounded-xl border border-dashed bg-muted/40 p-4 text-left transition-colors hover:bg-muted/70"
              >
                {file ? (
                  <>
                    <FileIcon className="h-5 w-5 shrink-0 text-muted-foreground" />
                    <span className="min-w-0 flex-1 truncate text-sm font-medium">
                      {file.name}
                    </span>
                  </>
                ) : (
                  <>
                    <UploadCloudIcon className="h-5 w-5 shrink-0 text-muted-foreground" />
                    <span className="flex-1 text-sm text-muted-foreground">
                      엑셀(.xlsx/.xls) 또는 PDF 파일 선택
                    </span>
                  </>
                )}
              </button>
            </div>

            {/* 수집·이용 동의 */}
            <label className="flex cursor-pointer items-start gap-3 rounded-xl bg-muted/40 p-4">
              <Checkbox
                checked={consent}
                onCheckedChange={(v) => setConsent(v === true)}
                className="mt-0.5"
                aria-label="개인정보 수집·이용 동의"
              />
              <span className="text-[13px] leading-relaxed text-muted-foreground">
                거래내역서에 포함된 정보(계좌·종목·금액 등)를 파싱 지원 개선 목적으로 수집·이용하는 데
                동의합니다. 파일은 관리자 검토 후 활용됩니다.
              </span>
            </label>
          </div>
        </FullScreenPanelBody>

        <FullScreenPanelFooter>
          <Button
            size="xl"
            className="w-full"
            onClick={handleSubmit}
            disabled={!canSubmit}
          >
            {submitting ? "제보 중..." : "제보하기"}
          </Button>
        </FullScreenPanelFooter>
      </FullScreenPanelContent>
    </FullScreenPanel>
  );
}
