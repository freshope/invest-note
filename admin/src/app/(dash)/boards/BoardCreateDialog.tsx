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
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/base/Select";
import { Button } from "@/components/base/Button";
import { Input } from "@/components/base/Input";
import { Label } from "@/components/base/Label";
import { BOARD_TYPES, boardListKey } from "@/components/board/constants";

// 게시판 글 작성(관리자 공지 등). board_type 선택 + title + body + is_pinned.
export function BoardCreateDialog({
  defaultBoardType,
}: {
  defaultBoardType: BoardType;
}) {
  const [open, setOpen] = useState(false);
  const queryClient = useQueryClient();
  const [boardType, setBoardType] = useState<BoardType>(defaultBoardType);
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
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">글 작성</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>게시판 글 작성</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="board_type">게시판(board_type)</Label>
            <Select
              value={boardType}
              onValueChange={(v) => setBoardType(v as BoardType)}
            >
              <SelectTrigger id="board_type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {BOARD_TYPES.map((b) => (
                  <SelectItem key={b.value} value={b.value}>
                    {b.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
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
