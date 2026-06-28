"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ChevronRightIcon } from "lucide-react";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  FullScreenPanelHeader,
  FullScreenPanelBody,
} from "@/components/base/FullScreenPanel";
import { EmptyCard } from "@/components/shared/EmptyCard";
import { ErrorState } from "@/components/shared/ErrorState";
import { boardApi, type MyPost, type MyPostBoardType } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { requestImportOpen } from "@/lib/import-deeplink";
import {
  TYPE_LABEL,
  STATUS_META,
  getPostDisplayTitle,
} from "@/lib/board-post";
import { formatDateOnly } from "@/lib/format";
import { cn } from "@/lib/utils";
import { MyPostDetailPanel } from "./MyPostDetailPanel";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  boardType: MyPostBoardType;
  title: string;
  /** 헤더 "작성" 버튼 → 작성 폼 패널 오픈. */
  onCompose: () => void;
}

/**
 * "내가 보낸 내역" 목록 메인 패널(공지 스타일 행: 미리보기 + 상태 칩 + 글별 읽기 점).
 * 행 클릭 → 상세 패널(스택). 헤더 "작성" → 별도 작성 폼 패널. 읽기 점은 서버 플래그(post.unread)이며
 * 상세 진입 시 서버 read 처리 + my-posts invalidate 로 갱신된다.
 */
export function MyPostsListPanel({
  open,
  onOpenChange,
  boardType,
  title,
  onCompose,
}: Props) {
  const router = useRouter();
  // 스냅샷 객체 대신 id 보관 후 live items 에서 조회 → 상세 열린 중 refetch 되면 새 답변 반영.
  const [detailId, setDetailId] = useState<string | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.myPosts,
    queryFn: () => boardApi.myPosts(),
    enabled: open,
  });

  const items = useMemo(
    () => (data?.items ?? []).filter((p) => p.board_type === boardType),
    [data, boardType],
  );
  // 서버 unread 플래그로 행 점 구성(단일 출처). invalidate 로 자연 갱신.
  const unreadIds = useMemo(
    () => new Set(items.filter((p) => p.unread === true).map((p) => p.id)),
    [items],
  );

  // useStaggeredPanel 이 닫힘 애니메이션 동안 payload 유지 → close 시 null 돼도 안전.
  const detailPost = detailId
    ? (items.find((p) => p.id === detailId) ?? null)
    : null;

  const goImport = () => {
    requestImportOpen();
    onOpenChange(false);
    router.push("/records");
  };

  return (
    <>
      <FullScreenPanel open={open} onOpenChange={onOpenChange}>
        <FullScreenPanelContent>
          <FullScreenPanelHeader
            title={title}
            action={
              <button
                type="button"
                onClick={onCompose}
                className="rounded-full px-3 h-9 text-[15px] font-semibold text-primary transition-colors hover:bg-primary/10"
              >
                작성
              </button>
            }
          />
          <FullScreenPanelBody>
            <div className="px-5 pt-2 pb-6">
              {isLoading ? (
                <div className="space-y-3 animate-pulse">
                  {[0, 1, 2].map((i) => (
                    <div key={i} className="h-16 rounded-2xl bg-muted/60" />
                  ))}
                </div>
              ) : isError ? (
                <ErrorState onRetry={refetch} />
              ) : items.length === 0 ? (
                <EmptyCard
                  title="보낸 내역이 없어요"
                  description="상단 ‘작성’ 으로 보내주시면 이곳에서 처리 상태와 답변을 확인할 수 있어요."
                />
              ) : (
                <div className="rounded-2xl bg-muted/60 overflow-hidden">
                  {items.map((post) => (
                    <PostRow
                      key={post.id}
                      post={post}
                      unread={unreadIds.has(post.id)}
                      onClick={() => setDetailId(post.id)}
                    />
                  ))}
                </div>
              )}
            </div>
          </FullScreenPanelBody>
        </FullScreenPanelContent>
      </FullScreenPanel>

      <MyPostDetailPanel
        post={detailPost}
        onClose={() => setDetailId(null)}
        onImport={goImport}
      />
    </>
  );
}

function PostRow({
  post,
  unread,
  onClick,
}: {
  post: MyPost;
  unread: boolean;
  onClick: () => void;
}) {
  const chip = STATUS_META[post.status];
  const displayTitle = getPostDisplayTitle(post);
  // 제목이 없으면(의견/오류 등) 본문을 대표 줄로. prefix 누출 방지를 위해 raw title 직접 미사용.
  const primary = displayTitle || post.body || TYPE_LABEL[post.board_type];
  const showBodyPreview = !!displayTitle && !!post.body;

  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-full items-center justify-between gap-3 border-t border-border/60 px-5 py-4 text-left transition-colors first:border-t-0 hover:bg-foreground/5"
    >
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          <span
            className={cn(
              "shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold",
              chip.className,
            )}
          >
            {chip.label}
          </span>
          <span className="truncate text-[15px] font-medium text-foreground">
            {primary}
          </span>
          {unread ? (
            <span
              className="size-1.5 shrink-0 rounded-full bg-primary"
              aria-label="안 읽음"
            />
          ) : null}
        </span>
        {showBodyPreview ? (
          <span className="mt-0.5 block line-clamp-2 text-[13px] text-muted-foreground">
            {post.body}
          </span>
        ) : null}
        <span className="mt-1 block text-[12px] text-muted-foreground tabular-nums">
          {formatDateOnly(post.created_at)}
        </span>
      </span>
      <ChevronRightIcon className="size-5 shrink-0 text-muted-foreground" />
    </button>
  );
}
