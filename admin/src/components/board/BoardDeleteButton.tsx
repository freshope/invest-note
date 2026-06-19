"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { adminApi, type BoardType, ApiError } from "@/lib/api";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from "@/components/base/Dialog";
import { Button } from "@/components/base/Button";
import { boardListKey } from "@/components/board/constants";

// 글 삭제(cascade). 삭제 후 목록 invalidate + /boards 이동.
export function BoardDeleteButton({
  postId,
  boardType,
}: {
  postId: string;
  boardType: BoardType;
}) {
  const [open, setOpen] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const router = useRouter();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => adminApi.boards.remove(postId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: boardListKey(boardType) });
      queryClient.invalidateQueries({ queryKey: ["admin", "stats"] });
      setOpen(false);
      router.push("/boards");
    },
    onError: (e) =>
      setErrorMsg(e instanceof ApiError ? e.message : "삭제에 실패했습니다."),
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="destructive" size="sm">
          글 삭제
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>삭제 확인</DialogTitle>
        </DialogHeader>
        <p className="text-[14px] text-muted-foreground">
          이 글과 모든 댓글·첨부가 삭제됩니다. 계속할까요?
        </p>
        {errorMsg && <p className="text-[13px] text-destructive">{errorMsg}</p>}
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline">
              취소
            </Button>
          </DialogClose>
          <Button
            variant="destructive"
            disabled={mutation.isPending}
            onClick={() => {
              setErrorMsg(null);
              mutation.mutate();
            }}
          >
            삭제
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
