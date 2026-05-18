"use client";

import { CheckCircle2Icon, XCircleIcon } from "lucide-react";
import { Button } from "@/components/base/Button";
import { FullScreenPanelFooter } from "@/components/base/FullScreenPanel";
import type { ImportCommitResponse } from "@/lib/api-client";

interface Props {
  result: ImportCommitResponse;
  onClose: () => void;
}

export function ResultStep({ result, onClose }: Props) {
  const success = result.error_count === 0;

  return (
    <div className="flex flex-col min-h-full">
      <div className="flex-1 px-5 pt-2 pb-4 flex flex-col items-center justify-center text-center space-y-5">
        {success ? (
          <CheckCircle2Icon className="h-14 w-14 text-green-500" />
        ) : (
          <XCircleIcon className="h-14 w-14 text-red-500" />
        )}

        <div>
          <p className="text-lg font-semibold">
            {success ? "등록 완료" : "일부 오류 발생"}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {result.inserted_count}건 신규 등록
            {result.merged_count > 0 && ` · ${result.merged_count}건 머지`}
            {result.skipped_count > 0 && ` · ${result.skipped_count}건 건너뜀`}
            {result.error_count > 0 && ` · ${result.error_count}건 실패`}
          </p>
        </div>

        {result.errors.length > 0 && (
          <ul className="w-full max-h-32 overflow-y-auto rounded-lg border bg-muted/30 p-2 text-left text-xs text-muted-foreground space-y-1">
            {result.errors.map((e, i) => (
              <li key={i}>{e.reason}</li>
            ))}
          </ul>
        )}
      </div>

      <FullScreenPanelFooter>
        <Button size="xl" className="w-full" onClick={onClose}>
          닫기
        </Button>
      </FullScreenPanelFooter>
    </div>
  );
}
