"use client";

import { useRef, useState } from "react";
import { ChevronDownIcon, ChevronUpIcon, ExternalLinkIcon, UploadCloudIcon } from "lucide-react";
import { Button } from "@/components/base/Button";
import { FullScreenPanelFooter } from "@/components/base/FullScreenPanel";
import { openExternal } from "@/lib/external-link";
import { isAcceptedExtension, type BrokerDownloadGuide } from "./brokers";

interface Props {
  brokerName: string;
  accept: string;
  downloadGuide?: BrokerDownloadGuide;
  onFileSelect: (file: File) => void;
  onBack?: () => void;
  isLoading: boolean;
}

export function FileStep({ brokerName, accept, downloadGuide, onFileSelect, onBack, isLoading }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [formatError, setFormatError] = useState<string | null>(null);
  // 다운로드 절차를 모르는 사용자가 많아 기본 열림으로 안내.
  const [guideOpen, setGuideOpen] = useState(true);

  const acceptLabel = accept.replace(/\./g, "").toUpperCase();

  const handleFile = (file: File) => {
    // accept 는 힌트일 뿐 드래그-드롭/일부 피커에서 강제 안 됨 → 확장자 직접 검증.
    if (!isAcceptedExtension(file.name, accept)) {
      setFormatError(`${acceptLabel} 형식만 업로드할 수 있어요.`);
      setSelectedFile(null);
      return;
    }
    setFormatError(null);
    setSelectedFile(file);
    onFileSelect(file);
  };

  const buttonLabel = isLoading ? "분석 중..." : "파일을 선택해주세요";

  return (
    <div className="flex flex-col min-h-full">
      <div className="flex-1 px-5 pt-2 pb-4 space-y-5">
        <div
          className={[
            "flex cursor-pointer flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed p-10 transition-colors",
            dragging
              ? "border-primary bg-primary/5"
              : "border-border hover:border-primary/50 hover:bg-muted/30",
          ].join(" ")}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const file = e.dataTransfer.files[0];
            if (file) handleFile(file);
          }}
        >
          <UploadCloudIcon className="h-10 w-10 text-muted-foreground" />
          <div className="text-center">
            <p className="text-sm font-medium">
              {brokerName} 거래내역서를 드래그하거나 클릭해서 선택하세요
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {acceptLabel} 형식 지원 · 암호 걸린 파일은 열 수 없어요
            </p>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept={accept}
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleFile(file);
            }}
          />
        </div>

        {formatError && (
          <p className="rounded-lg bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {formatError}
          </p>
        )}

        {selectedFile && (
          <div className="flex items-center gap-2 rounded-lg bg-muted/50 px-4 py-3 text-sm">
            <span className="font-medium text-foreground">{selectedFile.name}</span>
            <span className="text-muted-foreground">
              ({(selectedFile.size / 1024).toFixed(0)} KB)
            </span>
          </div>
        )}

        {downloadGuide && (
          <div>
            <button
              type="button"
              className="flex w-full items-center justify-between rounded-lg border px-4 py-3 text-sm"
              onClick={() => setGuideOpen((v) => !v)}
              aria-expanded={guideOpen}
            >
              <span className="font-medium">{brokerName} 거래내역서 다운로드 방법</span>
              {guideOpen ? (
                <ChevronUpIcon className="h-4 w-4" />
              ) : (
                <ChevronDownIcon className="h-4 w-4" />
              )}
            </button>
            {guideOpen && (
              <div className="mt-2 space-y-3 rounded-lg border bg-muted/30 p-4 text-sm">
                <p className="text-xs text-muted-foreground">{downloadGuide.description}</p>
                <ol className="list-decimal space-y-1.5 pl-5 text-foreground">
                  {downloadGuide.steps.map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ol>
                {downloadGuide.helpUrl && (
                  <button
                    type="button"
                    className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
                    onClick={() => openExternal(downloadGuide.helpUrl!)}
                  >
                    <ExternalLinkIcon className="h-3.5 w-3.5" />
                    {brokerName} 도움말 열기
                  </button>
                )}
              </div>
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
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={isLoading}
          >
            {buttonLabel}
          </Button>
        </div>
      </FullScreenPanelFooter>
    </div>
  );
}
