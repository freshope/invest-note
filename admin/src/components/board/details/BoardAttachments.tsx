"use client";

import type { BoardAttachment } from "@/lib/api";
import { fmtText, fmtNum } from "@/lib/format";
import { AttachmentDownloadButton } from "@/components/board/AttachmentDownloadButton";

// 첨부 목록 + 다운로드. emphasis=true 면 카드형(거래내역서 검토용).
export function BoardAttachments({
  attachments,
  emphasis = false,
}: {
  attachments: BoardAttachment[];
  emphasis?: boolean;
}) {
  return (
    <section className="space-y-2">
      <h2 className="text-[15px] font-semibold">첨부 ({attachments.length})</h2>
      {attachments.length === 0 ? (
        <p className="text-[14px] text-muted-foreground">첨부가 없습니다.</p>
      ) : (
        <ul className="space-y-1">
          {attachments.map((a) => (
            <li
              key={a.id}
              className={
                "flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-[14px] " +
                (emphasis ? "border-primary/30 bg-primary/5" : "border-border")
              }
            >
              <span className="min-w-0 flex-1 truncate">
                {fmtText(a.original_name)}
              </span>
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
  );
}
