"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { adminApi, ApiError } from "@/lib/api";
import { Button } from "@/components/base/Button";

// 첨부 다운로드 — presigned GET URL 을 받아 새 탭으로 연다.
export function AttachmentDownloadButton({ attachmentId }: { attachmentId: string }) {
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => adminApi.boards.attachmentDownloadUrl(attachmentId),
    onSuccess: ({ download_url }) => {
      window.open(download_url, "_blank", "noopener");
    },
    onError: (e) =>
      setErrorMsg(e instanceof ApiError ? e.message : "다운로드에 실패했습니다."),
  });

  return (
    <div className="flex items-center gap-2">
      {errorMsg && <span className="text-[12px] text-destructive">{errorMsg}</span>}
      <Button
        variant="outline"
        size="sm"
        disabled={mutation.isPending}
        onClick={() => {
          setErrorMsg(null);
          mutation.mutate();
        }}
      >
        다운로드
      </Button>
    </div>
  );
}
