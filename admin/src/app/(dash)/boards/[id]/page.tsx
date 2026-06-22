"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/lib/api";
import { ApiErrorState } from "@/components/ApiErrorState";
import { Button } from "@/components/base/Button";
import { fmtText, fmtNum, fmtDateTime } from "@/lib/format";
import {
  boardDetailKey,
  boardTypeLabel,
} from "@/components/board/constants";
import { BoardStatusControls } from "@/components/board/BoardStatusControls";
import { BoardCommentThread } from "@/components/board/BoardCommentThread";
import { BoardCommentForm } from "@/components/board/BoardCommentForm";
import { BoardDeleteButton } from "@/components/board/BoardDeleteButton";
import { AttachmentDownloadButton } from "@/components/board/AttachmentDownloadButton";

export default function BoardDetailPage() {
  const params = useParams<{ id: string }>();
  const postId = params.id;

  const { data, isLoading, error } = useQuery({
    queryKey: boardDetailKey(postId),
    queryFn: () => adminApi.boards.get(postId),
    enabled: !!postId,
  });

  if (error) return <ApiErrorState error={error} />;
  if (isLoading || !data) {
    return <p className="text-sm text-muted-foreground">불러오는 중...</p>;
  }

  const hasMetadata = Object.keys(data.metadata ?? {}).length > 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Button asChild variant="outline" size="sm">
          <Link href="/boards">← 목록</Link>
        </Button>
        <BoardDeleteButton postId={data.id} boardType={data.board_type} />
      </div>

      {/* 본문 */}
      <section className="space-y-3 rounded-lg border border-border p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold">{fmtText(data.title)}</h1>
            <p className="mt-1 text-[13px] text-muted-foreground">
              {boardTypeLabel(data.board_type)} · 작성자{" "}
              {fmtText(data.user_id)} · {fmtDateTime(data.created_at)}
            </p>
          </div>
        </div>
        <BoardStatusControls
          postId={data.id}
          boardType={data.board_type}
          status={data.status}
          isPinned={data.is_pinned}
        />
        <p className="whitespace-pre-wrap text-[14px]">{fmtText(data.body)}</p>
        {hasMetadata && (
          <div className="space-y-1">
            <span className="text-[13px] font-medium text-muted-foreground">
              metadata
            </span>
            <pre className="overflow-x-auto rounded-md bg-muted/40 p-3 text-[12px]">
              {JSON.stringify(data.metadata, null, 2)}
            </pre>
          </div>
        )}
      </section>

      {/* 첨부(메타 + 다운로드). type/broker/country 는 위 metadata 뷰어에 표시됨. */}
      <section className="space-y-2">
        <h2 className="text-[15px] font-semibold">
          첨부 ({data.attachments.length})
        </h2>
        {data.attachments.length === 0 ? (
          <p className="text-[14px] text-muted-foreground">첨부가 없습니다.</p>
        ) : (
          <ul className="space-y-1">
            {data.attachments.map((a) => (
              <li
                key={a.id}
                className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2 text-[14px]"
              >
                <span className="min-w-0 flex-1 truncate">{fmtText(a.original_name)}</span>
                <div className="flex shrink-0 items-center gap-3">
                  <span className="tabular-nums text-[13px] text-muted-foreground">
                    {a.size_bytes != null ? `${fmtNum(a.size_bytes)} B` : "-"}
                  </span>
                  <AttachmentDownloadButton attachmentId={a.id} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* 댓글 스레드 + 관리자 댓글 작성 */}
      <section className="space-y-3">
        <h2 className="text-[15px] font-semibold">
          댓글 ({data.comments.length})
        </h2>
        <BoardCommentThread
          postId={data.id}
          boardType={data.board_type}
          comments={data.comments}
        />
        <BoardCommentForm postId={data.id} boardType={data.board_type} />
      </section>
    </div>
  );
}
