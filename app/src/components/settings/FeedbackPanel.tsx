"use client";

import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
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
import { queryKeys } from "@/lib/query-keys";

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
  const queryClient = useQueryClient();
  const [body, setBody] = useState("");
  const [wasOpen, setWasOpen] = useState(open);

  // 진입(open false→true) 시마다 폼을 초기 상태로 — 패널 컴포넌트는 항상 마운트되어 있어
  // 직전 입력값이 useState 에 남기 때문. effect 동기 setState 대신 렌더 중 조정(React 공식 패턴).
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) setBody("");
  }

  const mutation = useMutation({
    mutationFn: (input: FeedbackInput) => boardApi.submitFeedback(input),
    onSuccess: () => {
      toast.success("의견이 전송되었습니다. 감사합니다!");
      queryClient.invalidateQueries({ queryKey: queryKeys.myPosts });
      setBody("");
      onOpenChange(false);
    },
    onError: (err) => {
      toast.error(errorMessage(err));
    },
  });

  const trimmed = body.trim();
  const canSubmit = trimmed.length > 0 && !mutation.isPending;

  // 동기 재진입 락 — mutation.isPending 은 리렌더가 커밋되기 전까지 stale 값이라, 버튼을
  // 빠르게 연타하면 옛 값(false)을 읽고 mutate 가 여러 번 발사돼 중복 의견이 쌓인다.
  // ref 는 즉시 반영되므로 첫 클릭만 통과시키고, mutate 종료(onSettled) 시 해제한다.
  const submittingRef = useRef(false);

  const handleSubmit = () => {
    if (!canSubmit) return;
    if (submittingRef.current) return;
    submittingRef.current = true;
    mutation.mutate(
      { body: trimmed },
      { onSettled: () => { submittingRef.current = false; } },
    );
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
