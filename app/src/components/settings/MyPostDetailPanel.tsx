"use client";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { FileIcon, DownloadIcon } from "lucide-react";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  FullScreenPanelHeader,
  FullScreenPanelBody,
  useStaggeredPanel,
} from "@/components/base/FullScreenPanel";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/base/Dialog";
import { Button } from "@/components/base/Button";
import { boardApi, type MyPost, type MyPostAttachment } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import {
  TYPE_LABEL,
  STATUS_META,
  formatFileSize,
  isImageAttachment,
} from "@/lib/board-post";
import { formatDateOnly } from "@/lib/format";
import { openExternal } from "@/lib/external-link";
import { cn } from "@/lib/utils";

interface Props {
  /** null 이면 상세 닫힘. 목록에서 선택한 글 객체를 그대로 받는다(별도 fetch 없음). */
  post: MyPost | null;
  onClose: () => void;
  /** broker_statement resolved 가져오기 CTA. */
  onImport: () => void;
}

/**
 * 내 제보/문의 상세 패널(목록→상세 스택). my-posts 응답 글 객체를 그대로 표시 —
 * by-id 엔드포인트가 없으므로 fetch 하지 않는다. 본문 전체 + 상태 + 첨부 + 어드민 댓글.
 */
export function MyPostDetailPanel({ post, onClose, onImport }: Props) {
  // 닫힘 애니메이션 동안 payload 유지(NoticeDetailHost 패턴).
  const { open, payload, remountKey } = useStaggeredPanel(post);
  if (payload === null) return null;
  return (
    <FullScreenPanel open={open} onOpenChange={onClose}>
      <FullScreenPanelContent key={`mypost-${remountKey}`}>
        <DetailContent post={payload} onImport={onImport} />
      </FullScreenPanelContent>
    </FullScreenPanel>
  );
}

function DetailContent({ post, onImport }: { post: MyPost; onImport: () => void }) {
  const queryClient = useQueryClient();
  // 상세 진입 시 서버 읽음 처리 → my-posts invalidate 로 점 해제. POST 성공 후 invalidate(race 회피).
  // 이미 읽음(unread!==true)이면 skip — 안 그러면 핫패스(상세 열 때마다) my-posts 전체 재조회 +
  // 첨부 presigned URL 재서명이 무의미하게 반복된다. unread 가 true→false 로 바뀌면 가드가 막아 루프 없음.
  useEffect(() => {
    if (post.unread !== true) return;
    boardApi
      .markPostRead(post.id)
      .then(() =>
        queryClient.invalidateQueries({ queryKey: queryKeys.myPosts }),
      )
      .catch(() => {});
  }, [post.id, post.unread, queryClient]);

  const [lightbox, setLightbox] = useState<string | null>(null);

  const chip = STATUS_META[post.status];
  const adminComments = post.comments.filter((c) => c.is_admin);
  // BE 가 아직 attachments 를 안 줄 수 있어 가드(undefined → []).
  const attachments = post.attachments ?? [];
  // 이미지(라이트박스) vs 그 외(다운로드). content_type + 확장자 폴백(모바일 octet-stream 대응).
  const images = attachments.filter(isImageAttachment);
  const files = attachments.filter((a) => !isImageAttachment(a));
  const showImportCta =
    post.board_type === "broker_statement" && post.status === "resolved";
  // 헤더는 목록처럼 게시판명. 증권사명은 첫 줄 상태 옆으로(거래내역서 제보 한정).
  const headerTitle = TYPE_LABEL[post.board_type];
  const showBroker =
    post.board_type === "broker_statement" && !!post.metadata.broker;

  return (
    <>
      <FullScreenPanelHeader title={headerTitle} />
      <FullScreenPanelBody>
        <div className="px-5 pt-2 pb-8 space-y-5">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold",
                chip.className,
              )}
            >
              {chip.label}
            </span>
            {showBroker ? (
              <span className="truncate text-[14px] font-medium text-foreground">
                {post.metadata.broker}
              </span>
            ) : null}
            <span className="ml-auto text-[12px] text-muted-foreground tabular-nums">
              {formatDateOnly(post.created_at)}
            </span>
          </div>

          {post.body ? (
            <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-foreground/90">
              {post.body}
            </p>
          ) : null}

          {attachments.length > 0 ? (
            <section className="space-y-2">
              <h3 className="text-[13px] font-semibold text-muted-foreground">
                첨부파일
              </h3>
              {images.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {images.map((a) => (
                    <button
                      key={a.id}
                      type="button"
                      onClick={() => setLightbox(a.url)}
                      className="size-24 overflow-hidden rounded-xl border border-border/60 bg-muted/40"
                      aria-label={`${a.original_name} 크게 보기`}
                    >
                      {/* 정적 export + presigned URL 이라 next/image 부적합 — 순수 img */}
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={a.url}
                        alt={a.original_name}
                        className="size-full object-cover"
                      />
                    </button>
                  ))}
                </div>
              ) : null}
              {files.map((a) => (
                <FileRow key={a.id} attachment={a} />
              ))}
            </section>
          ) : null}

          {adminComments.length > 0 ? (
            <section className="space-y-2">
              <h3 className="text-[13px] font-semibold text-muted-foreground">
                운영자 답변
              </h3>
              <div className="space-y-2 rounded-xl bg-muted/60 p-4">
                {adminComments.map((c) => (
                  <div key={c.id} className="space-y-0.5">
                    <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-foreground/90">
                      {c.body}
                    </p>
                    <p className="text-[11px] text-muted-foreground tabular-nums">
                      {formatDateOnly(c.created_at)}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {showImportCta ? (
            <div className="space-y-2 rounded-xl bg-primary/5 p-4">
              <p className="text-[14px] font-medium text-foreground">
                🎉 제보해주신 거래내역서, 이제 일괄등록이 가능해요!
              </p>
              <Button size="lg" className="w-full" onClick={onImport}>
                지금 가져오기
              </Button>
            </div>
          ) : null}
        </div>
      </FullScreenPanelBody>

      <Dialog open={lightbox !== null} onOpenChange={(o) => !o && setLightbox(null)}>
        <DialogContent
          aria-describedby={undefined}
          className="max-w-[92vw] border-0 bg-transparent p-0 shadow-none ring-0 sm:max-w-lg"
        >
          <DialogTitle className="sr-only">첨부 이미지</DialogTitle>
          {lightbox ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={lightbox}
              alt="첨부 이미지"
              className="max-h-[80vh] w-full rounded-lg object-contain"
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}

function FileRow({ attachment }: { attachment: MyPostAttachment }) {
  // size_bytes 는 nullable — 있을 때만 표시.
  const size =
    attachment.size_bytes != null ? formatFileSize(attachment.size_bytes) : "";
  return (
    <button
      type="button"
      onClick={() => openExternal(attachment.url)}
      className="flex w-full items-center gap-3 rounded-xl border border-border/60 bg-muted/40 p-3 text-left transition-colors hover:bg-muted/70"
    >
      <FileIcon className="size-5 shrink-0 text-muted-foreground" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[14px] font-medium text-foreground">
          {attachment.original_name}
        </span>
        {size ? (
          <span className="block text-[12px] text-muted-foreground tabular-nums">
            {size}
          </span>
        ) : null}
      </span>
      <DownloadIcon className="size-5 shrink-0 text-muted-foreground" />
    </button>
  );
}
