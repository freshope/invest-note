"use client";

import type { BoardDetail } from "@/lib/api";
import { fmtText, fmtDateTime } from "@/lib/format";
import { boardTypeLabel } from "@/components/board/constants";
import { BoardStatusControls } from "@/components/board/BoardStatusControls";
import { BoardCommentThread } from "@/components/board/BoardCommentThread";
import { BoardCommentForm } from "@/components/board/BoardCommentForm";
import { AuthorCell } from "@/components/AuthorCell";
import { BoardDetailShell } from "./BoardDetailShell";
import { BoardAttachments } from "./BoardAttachments";

// 사용자 의견 / 오류 신고 = 사용자 제보 triage. 상태 워크플로 + 관리자 답변(댓글) 중심.
export function TriageDetail({
  data,
  slug,
}: {
  data: BoardDetail;
  slug: string;
}) {
  return (
    <BoardDetailShell data={data} slug={slug}>
      <section className="space-y-3 rounded-lg border border-border p-4">
        <div>
          <h1 className="text-xl font-bold">{fmtText(data.title)}</h1>
          <p className="mt-1 text-[13px] text-muted-foreground">
            {boardTypeLabel(data.board_type)} · 작성자{" "}
            <AuthorCell
              avatarUrl={data.author_avatar_url}
              displayName={data.author_display_name}
              fallback="회원 미상"
            />{" "}
            · {fmtDateTime(data.created_at)}
          </p>
        </div>
        <BoardStatusControls
          postId={data.id}
          boardType={data.board_type}
          status={data.status}
          isPinned={data.is_pinned}
        />
        <p className="whitespace-pre-wrap text-[14px]">{fmtText(data.body)}</p>
      </section>

      {data.attachments.length > 0 && (
        <BoardAttachments attachments={data.attachments} />
      )}

      <section className="space-y-3">
        <h2 className="text-[15px] font-semibold">
          답변 ({data.comments.length})
        </h2>
        <BoardCommentThread
          postId={data.id}
          boardType={data.board_type}
          comments={data.comments}
        />
        <BoardCommentForm postId={data.id} boardType={data.board_type} />
      </section>
    </BoardDetailShell>
  );
}
