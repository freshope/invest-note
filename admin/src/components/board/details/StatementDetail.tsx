"use client";

import type { BoardDetail } from "@/lib/api";
import { fmtText, fmtDateTime } from "@/lib/format";
import { BoardStatusControls } from "@/components/board/BoardStatusControls";
import { BoardCommentThread } from "@/components/board/BoardCommentThread";
import { BoardCommentForm } from "@/components/board/BoardCommentForm";
import { statementTypeLabel } from "@/components/board/constants";
import { AuthorCell } from "@/components/AuthorCell";
import { BoardDetailShell } from "./BoardDetailShell";
import { BoardAttachments } from "./BoardAttachments";

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="space-y-0.5">
      <dt className="text-[12px] font-medium text-muted-foreground">{label}</dt>
      <dd className="text-[14px]">{value}</dd>
    </div>
  );
}

// 거래내역서 제출 = 파일 업로드 검토. metadata 구조화 표시 + 첨부 다운로드 강조 + 검토 상태.
export function StatementDetail({
  data,
  slug,
}: {
  data: BoardDetail;
  slug: string;
}) {
  const m = data.metadata ?? {};
  const consent = m.consent === true ? "동의함" : "-";

  return (
    <BoardDetailShell data={data} slug={slug}>
      <section className="space-y-4 rounded-lg border border-border p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-lg font-bold">{fmtText(data.title)}</h1>
            <p className="mt-1 text-[13px] text-muted-foreground">
              작성자{" "}
              <AuthorCell
                avatarUrl={data.author_avatar_url}
                displayName={data.author_display_name}
                fallback="회원 미상"
              />{" "}
              · {fmtDateTime(data.created_at)}
            </p>
          </div>
        </div>

        <div className="space-y-1">
          <BoardStatusControls
            postId={data.id}
            boardType={data.board_type}
            status={data.status}
            isPinned={data.is_pinned}
            showPin={false}
          />
          <p className="text-[12px] text-muted-foreground">
            반려 시 사유는 아래 댓글로 남겨주세요.
          </p>
        </div>

        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
          <Field label="제보 유형" value={statementTypeLabel(m.type)} />
          <Field label="증권사" value={fmtText(m.broker)} />
          <Field label="국가" value={fmtText(m.country)} />
          <Field label="동의" value={consent} />
        </dl>
      </section>

      <BoardAttachments attachments={data.attachments} emphasis />

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
    </BoardDetailShell>
  );
}
