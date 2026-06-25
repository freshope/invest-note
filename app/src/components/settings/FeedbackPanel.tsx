"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
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
import { boardApi, ApiError, type FeedbackInput } from "@/lib/api-client";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const MAX_LEN = 1000;

function errorMessage(err: unknown): string {
  if (err instanceof ApiError && err.status === 429) {
    return "의견이 너무 잦습니다. 잠시 후 다시 보내주세요.";
  }
  return "의견 전송 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.";
}

export function FeedbackPanel({ open, onOpenChange }: Props) {
  const [body, setBody] = useState("");

  const mutation = useMutation({
    mutationFn: (input: FeedbackInput) => boardApi.submitFeedback(input),
    onSuccess: () => {
      toast.success("의견이 전송되었습니다. 감사합니다!");
      setBody("");
      onOpenChange(false);
    },
    onError: (err) => {
      toast.error(errorMessage(err));
    },
  });

  const trimmed = body.trim();
  const canSubmit = trimmed.length > 0 && !mutation.isPending;

  const handleSubmit = () => {
    if (!canSubmit) return;
    mutation.mutate({ body: trimmed });
  };

  return (
    <FullScreenPanel open={open} onOpenChange={onOpenChange}>
      <FullScreenPanelContent>
        <FullScreenPanelHeader title="의견 보내기" />
        <FullScreenPanelBody>
          <div className="px-5 pt-2 pb-4 space-y-3">
            <p className="text-sm text-muted-foreground leading-relaxed">
              앱을 사용하면서 느낀 점이나 개선 아이디어를 자유롭게 남겨주세요.
              보내주신 의견은 서비스 개선에 활용됩니다.
            </p>
            <Textarea
              value={body}
              onChange={(e) => setBody(e.target.value.slice(0, MAX_LEN))}
              placeholder="의견을 입력해주세요"
              className="min-h-[160px]"
              maxLength={MAX_LEN}
            />
            <p className="text-right text-[12px] text-muted-foreground tabular-nums">
              {body.length}/{MAX_LEN}
            </p>
          </div>
        </FullScreenPanelBody>

        <FullScreenPanelFooter>
          <Button
            size="xl"
            className="w-full"
            onClick={handleSubmit}
            disabled={!canSubmit}
          >
            {mutation.isPending ? "전송 중..." : "보내기"}
          </Button>
        </FullScreenPanelFooter>
      </FullScreenPanelContent>
    </FullScreenPanel>
  );
}
