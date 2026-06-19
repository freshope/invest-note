"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { adminApi, type BoardType, ApiError } from "@/lib/api";
import { Button } from "@/components/base/Button";
import { boardDetailKey, boardListKey } from "@/components/board/constants";

// 관리자 댓글 작성(POST /admin/boards/{id}/comments → is_admin=true).
export function BoardCommentForm({
  postId,
  boardType,
}: {
  postId: string;
  boardType: BoardType;
}) {
  const queryClient = useQueryClient();
  const [body, setBody] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (text: string) => adminApi.boards.addComment(postId, { body: text }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: boardDetailKey(postId) });
      queryClient.invalidateQueries({ queryKey: boardListKey(boardType) });
      setBody("");
    },
    onError: (e) =>
      setErrorMsg(e instanceof ApiError ? e.message : "댓글 작성에 실패했습니다."),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrorMsg(null);
    if (!body.trim()) return;
    mutation.mutate(body);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-2">
      <textarea
        rows={3}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="관리자 댓글 작성"
        className="flex w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      />
      {errorMsg && <p className="text-[13px] text-destructive">{errorMsg}</p>}
      <div className="flex justify-end">
        <Button type="submit" size="sm" disabled={mutation.isPending || !body.trim()}>
          {mutation.isPending ? "등록 중..." : "댓글 등록"}
        </Button>
      </div>
    </form>
  );
}
