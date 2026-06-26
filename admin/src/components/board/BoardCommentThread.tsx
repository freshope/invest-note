"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  adminApi,
  type BoardType,
  type BoardComment,
  ApiError,
} from "@/lib/api";
import { Button } from "@/components/base/Button";
import { fmtDateTime } from "@/lib/format";
import { AuthorCell } from "@/components/AuthorCell";
import { boardDetailKey, boardListKey } from "@/components/board/constants";

function CommentDeleteButton({
  commentId,
  postId,
  boardType,
}: {
  commentId: string;
  postId: string;
  boardType: BoardType;
}) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => adminApi.boards.removeComment(commentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: boardDetailKey(postId) });
      queryClient.invalidateQueries({ queryKey: boardListKey(boardType) });
    },
  });
  return (
    <div className="flex items-center gap-2">
      {mutation.isError && (
        <span className="text-[12px] text-destructive">
          {mutation.error instanceof ApiError ? mutation.error.message : "삭제 실패"}
        </span>
      )}
      <Button
        variant="ghost"
        size="xs"
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        삭제
      </Button>
    </div>
  );
}

// 댓글 스레드. is_admin 댓글은 강조 표시. 작성자는 user_id 만(어드민 users 에 email 없음).
export function BoardCommentThread({
  postId,
  boardType,
  comments,
}: {
  postId: string;
  boardType: BoardType;
  comments: BoardComment[];
}) {
  if (comments.length === 0) {
    return <p className="text-[14px] text-muted-foreground">댓글이 없습니다.</p>;
  }
  return (
    <ul className="space-y-3">
      {comments.map((c) => (
        <li
          key={c.id}
          className={
            "rounded-lg border px-3 py-2 " +
            (c.is_admin
              ? "border-primary/30 bg-primary/5"
              : "border-border bg-muted/30")
          }
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-[13px] font-medium">
              {c.is_admin ? (
                "관리자"
              ) : (
                <AuthorCell
                  avatarUrl={c.author_avatar_url}
                  displayName={c.author_display_name}
                  fallback={c.user_id ?? "작성자 미상"}
                />
              )}
            </span>
            <div className="flex items-center gap-2">
              <span className="text-[12px] text-muted-foreground">
                {fmtDateTime(c.created_at)}
              </span>
              <CommentDeleteButton
                commentId={c.id}
                postId={postId}
                boardType={boardType}
              />
            </div>
          </div>
          <p className="mt-1 whitespace-pre-wrap text-[14px]">{c.body}</p>
        </li>
      ))}
    </ul>
  );
}
