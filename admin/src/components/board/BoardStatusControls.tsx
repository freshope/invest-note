"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  adminApi,
  type BoardType,
  type BoardPostUpdateInput,
  ApiError,
} from "@/lib/api";
import { Button } from "@/components/base/Button";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/base/Select";
import {
  BOARD_STATUSES,
  boardDetailKey,
  boardListKey,
} from "@/components/board/constants";

// 상태 변경(select) + 상단 고정 토글(PATCH). board_type 은 수정 불가(PATCH 미포함).
export function BoardStatusControls({
  postId,
  boardType,
  status,
  isPinned,
}: {
  postId: string;
  boardType: BoardType;
  status: string;
  isPinned: boolean;
}) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (input: BoardPostUpdateInput) =>
      adminApi.boards.update(postId, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: boardDetailKey(postId) });
      queryClient.invalidateQueries({ queryKey: boardListKey(boardType) });
    },
  });

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2">
        <span className="text-[13px] text-muted-foreground">상태</span>
        <Select
          value={status}
          onValueChange={(v) => mutation.mutate({ status: v })}
        >
          <SelectTrigger className="w-[130px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {/* BE status 는 자유 텍스트 — BOARD_STATUSES 밖 값(향후 app-side 작성 등)도
                트리거에 보이도록 fallback 항목으로 노출(공백 트리거 방지). */}
            {!BOARD_STATUSES.some((s) => s.value === status) && (
              <SelectItem value={status}>{status}</SelectItem>
            )}
            {BOARD_STATUSES.map((s) => (
              <SelectItem key={s.value} value={s.value}>
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <Button
        variant="outline"
        size="sm"
        disabled={mutation.isPending}
        onClick={() => mutation.mutate({ is_pinned: !isPinned })}
      >
        {isPinned ? "고정 해제" : "상단 고정"}
      </Button>
      {mutation.isError && (
        <span className="text-[13px] text-destructive">
          {mutation.error instanceof ApiError
            ? mutation.error.message
            : "변경 실패"}
        </span>
      )}
    </div>
  );
}
