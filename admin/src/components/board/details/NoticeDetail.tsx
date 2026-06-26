"use client";

import type { BoardDetail } from "@/lib/api";
import { fmtText, fmtDateTime } from "@/lib/format";
import { BoardStatusControls } from "@/components/board/BoardStatusControls";
import { BoardDetailShell } from "./BoardDetailShell";

// 공지 = 관리자 발신. 제목/본문/작성일 + 상단 고정 토글(상태 워크플로·댓글 없음).
export function NoticeDetail({
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
            {data.is_pinned && "📌 "}
            {fmtDateTime(data.created_at)}
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
    </BoardDetailShell>
  );
}
