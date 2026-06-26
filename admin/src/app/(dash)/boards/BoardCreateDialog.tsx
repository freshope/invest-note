"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  adminApi,
  type BoardType,
  type BoardPostCreateInput,
  ApiError,
} from "@/lib/api";
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
import { Input } from "@/components/base/Input";
import { Label } from "@/components/base/Label";
import { boardListKey, boardTypeLabel } from "@/components/board/constants";

// 게시판 글 작성(관리자 공지 등). board_type 은 진입한 게시판으로 고정.
export function BoardCreateDialog({ boardType }: { boardType: BoardType }) {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [isPinned, setIsPinned] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (input: BoardPostCreateInput) => adminApi.boards.create(input),
    onSuccess: (row) => {
      queryClient.invalidateQueries({ queryKey: boardListKey(row.board_type) });
      queryClient.invalidateQueries({ queryKey: ["admin", "stats"] });
      setOpen(false);
      setTitle("");
      setBody("");
      setIsPinned(false);
    },
    onError: (e) =>
      setErrorMsg(e instanceof ApiError ? e.message : "생성에 실패했습니다."),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrorMsg(null);
    mutation.mutate({
      board_type: boardType,
      title,
      body: body || undefined,
      is_pinned: isPinned,
    });
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setErrorMsg(null); // 닫을 때 이전 실패 메시지 초기화(재오픈 시 stale 방지)
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm">글 작성</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{boardTypeLabel(boardType)} 글 작성</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="title">제목 (title)</Label>
            <Input
              id="title"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="body">본문 (body)</Label>
            <textarea
              id="body"
              rows={5}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          </div>
          <label className="flex items-center gap-2 text-[14px]">
            <input
              type="checkbox"
              checked={isPinned}
              onChange={(e) => setIsPinned(e.target.checked)}
            />
            상단 고정(is_pinned)
          </label>

          {errorMsg && <p className="text-[13px] text-destructive">{errorMsg}</p>}

          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline">
                취소
              </Button>
            </DialogClose>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "생성 중..." : "생성"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
