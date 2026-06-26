"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ImageIcon, XIcon } from "lucide-react";
import { toast } from "sonner";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  FullScreenPanelHeader,
  FullScreenPanelBody,
  FullScreenPanelFooter,
} from "@/components/base/FullScreenPanel";
import { Button } from "@/components/base/Button";
import { Textarea } from "@/components/base/Textarea";
import { boardApi, ApiError } from "@/lib/api-client";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const MAX_LEN = 1000;
// presign 게이트(10MB)와 동일 — presign 이전 즉시 피드백.
const MAX_SIZE_BYTES = 10 * 1024 * 1024;
// BE 스키마(MAX_BUG_REPORT_ATTACHMENTS)와 동일 — 초과 선택 시 클라에서 미리 차단.
const MAX_FILES = 5;
const ACCEPT = "image/png,image/jpeg,image/webp,image/heic";

function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    switch (err.status) {
      case 413:
        return "이미지가 너무 큽니다. 10MB 이하로 첨부해주세요.";
      case 415:
        return "지원하지 않는 이미지 형식입니다. PNG/JPG/WEBP/HEIC 파일을 첨부해주세요.";
      case 429:
        return "신고가 너무 잦습니다. 잠시 후 다시 시도해주세요.";
      case 503:
        return "지금은 신고를 받을 수 없습니다. 잠시 후 다시 시도해주세요.";
      case 400:
      case 403:
        return "이미지 업로드가 완료되지 않았습니다. 다시 시도해주세요.";
    }
  }
  return "오류 신고 중 문제가 발생했습니다. 잠시 후 다시 시도해주세요.";
}

export function BugReportPanel({ open, onOpenChange }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [body, setBody] = useState("");
  const [files, setFiles] = useState<File[]>([]);

  // 진입(open) 시마다 폼을 초기 상태로 — 패널 컴포넌트는 항상 마운트되어 있어
  // 직전 입력값이 useState 에 남기 때문. files 리셋 시 previews 는 아래 effect 가 정리.
  useEffect(() => {
    if (open) {
      setBody("");
      setFiles([]);
    }
  }, [open]);

  // 첨부 썸네일 — files 마다 object URL 생성, 변경/언마운트 시 전부 revoke(메모리 누수 방지).
  const [previews, setPreviews] = useState<string[]>([]);
  useEffect(() => {
    const urls = files.map((f) => URL.createObjectURL(f));
    setPreviews(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [files]);

  const removeAt = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const mutation = useMutation({
    mutationFn: async ({ body, files }: { body: string; files: File[] }) => {
      // 파일별 presign→PUT 을 병렬 실행(temp key 독립). Promise.all 은 입력 순서를
      // 보존하므로 attachments 배열 순서도 유지. content_type 은 세 곳에 동일하게 흘린다.
      const attachments = await Promise.all(
        files.map(async (f) => {
          const contentType = f.type || "application/octet-stream";
          const meta = {
            original_name: f.name,
            content_type: contentType,
            size_bytes: f.size,
          };
          const presigned = await boardApi.presign(meta);
          await boardApi.uploadToR2(presigned.upload_url, f, contentType);
          return { ...meta, storage_key: presigned.storage_key };
        }),
      );
      await boardApi.submitBugReport(
        attachments.length ? { body, attachments } : { body },
      );
    },
    onSuccess: () => {
      toast.success("오류 신고가 접수되었습니다. 감사합니다!");
      setBody("");
      setFiles([]);
      onOpenChange(false);
    },
    onError: (err) => {
      toast.error(errorMessage(err));
    },
  });

  const handleFilePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files ?? []);
    // 동일 파일 재선택도 다시 잡히도록 매번 input 을 비운다.
    e.target.value = "";
    if (picked.length === 0) return;

    const room = MAX_FILES - files.length;
    if (room <= 0) {
      toast.error(`스크린샷은 최대 ${MAX_FILES}장까지 첨부할 수 있어요.`);
      return;
    }
    // 두 사유(10MB 초과 / 장수 초과)는 동시에 발생할 수 있으므로 각각 독립 안내한다.
    const sized = picked.filter((f) => f.size <= MAX_SIZE_BYTES);
    const accepted = sized.slice(0, room);
    if (sized.length < picked.length) {
      toast.error("일부 이미지가 장당 10MB 를 넘어 제외했어요.");
    }
    if (sized.length > room) {
      toast.error(`스크린샷은 최대 ${MAX_FILES}장까지 첨부할 수 있어요.`);
    }
    if (accepted.length > 0) {
      setFiles((prev) => [...prev, ...accepted]);
    }
  };

  const trimmed = body.trim();
  const canSubmit = trimmed.length > 0 && !mutation.isPending;

  const handleSubmit = () => {
    if (!canSubmit) return;
    mutation.mutate({ body: trimmed, files });
  };

  return (
    <FullScreenPanel open={open} onOpenChange={onOpenChange}>
      <FullScreenPanelContent>
        <FullScreenPanelHeader title="오류 신고" />
        <FullScreenPanelBody>
          <div className="px-5 pt-2 pb-4 space-y-4">
            <p className="text-sm text-muted-foreground leading-relaxed">
              앱에서 발생한 오류나 이상한 동작을 알려주세요. 화면을 캡처한
              스크린샷을 함께 첨부하면 더 빠르게 확인할 수 있습니다.
            </p>

            <Textarea
              value={body}
              onChange={(e) => setBody(e.target.value.slice(0, MAX_LEN))}
              placeholder="어떤 문제가 있었는지 설명해주세요"
              className="min-h-[140px]"
              maxLength={MAX_LEN}
            />
            <p className="-mt-2 text-right text-[12px] text-muted-foreground tabular-nums">
              {body.length}/{MAX_LEN}
            </p>

            <div className="space-y-2">
              <input
                ref={fileInputRef}
                type="file"
                accept={ACCEPT}
                multiple
                className="hidden"
                onChange={handleFilePick}
              />

              {files.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {files.map((f, i) => (
                    <div
                      key={`${f.name}-${f.size}-${i}`}
                      className="relative size-20 overflow-hidden rounded-xl border border-border/60 bg-muted/40"
                    >
                      {previews[i] ? (
                        // 정적 export + blob URL 이라 next/image 부적합 — 순수 img 사용.
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={previews[i]}
                          alt={f.name}
                          className="size-full object-cover"
                        />
                      ) : (
                        <div className="flex size-full items-center justify-center">
                          <ImageIcon className="h-5 w-5 text-muted-foreground" />
                        </div>
                      )}
                      <button
                        type="button"
                        onClick={() => removeAt(i)}
                        className="absolute right-1 top-1 flex size-5 items-center justify-center rounded-full bg-black/55 text-white transition-colors hover:bg-black/75"
                        aria-label="첨부 이미지 제거"
                      >
                        <XIcon className="size-3" />
                      </button>
                    </div>
                  ))}
                </div>
              ) : null}

              {files.length < MAX_FILES ? (
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="flex w-full items-center gap-3 rounded-xl border border-dashed bg-muted/40 p-4 text-left transition-colors hover:bg-muted/70"
                >
                  <ImageIcon className="h-5 w-5 shrink-0 text-muted-foreground" />
                  <span className="flex-1 text-sm text-muted-foreground">
                    스크린샷 첨부 (선택 · {files.length}/{MAX_FILES})
                  </span>
                </button>
              ) : null}
            </div>
          </div>
        </FullScreenPanelBody>

        <FullScreenPanelFooter>
          <Button
            size="xl"
            className="w-full"
            onClick={handleSubmit}
            disabled={!canSubmit}
          >
            {mutation.isPending ? "전송 중..." : "신고하기"}
          </Button>
        </FullScreenPanelFooter>
      </FullScreenPanelContent>
    </FullScreenPanel>
  );
}
