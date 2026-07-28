"use client";

import { useEffect, useRef, useState } from "react";
import {
  useInfiniteQuery,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ChevronRightIcon } from "lucide-react";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  FullScreenPanelHeader,
  FullScreenPanelBody,
  useStaggeredPanel,
} from "@/components/base/FullScreenPanel";
import { EmptyCard } from "@/components/shared/EmptyCard";
import { ErrorState } from "@/components/shared/ErrorState";
import { LoadMoreButton } from "@/components/shared/LoadMoreButton";
import { MyPostDetailContent } from "@/components/settings/MyPostDetailPanel";
import { NoticePanel } from "@/components/settings/NoticePanel";
import {
  boardApi,
  notificationApi,
  type NotificationFeedItem,
  type MyPostBoardType,
} from "@/lib/api-client";
import { offsetNextPageParam } from "@/lib/infinite-list";
import { queryKeys } from "@/lib/query-keys";
import { requestImportOpen } from "@/lib/import-deeplink";
import { TYPE_LABEL } from "@/lib/board-post";
import { formatDateOnly } from "@/lib/format";
import { cn } from "@/lib/utils";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// 딥링크 대상 게시판 타입 판정(board_type 은 서버에서 string|null 로 옴).
const MY_POST_BOARD_TYPES: MyPostBoardType[] = [
  "feedback",
  "bug_report",
  "broker_statement",
];
function isMyPostBoardType(v: string | null): v is MyPostBoardType {
  return v !== null && (MY_POST_BOARD_TYPES as string[]).includes(v);
}

// 딥링크 상태: notification → 해당 게시판 상세(비대칭 딥링크, 특정 글까지) / notice → 공지 목록.
type Deeplink =
  | { kind: "post"; boardType: MyPostBoardType; postId: string }
  | { kind: "notice" }
  | null;

const EMPTY_UNREAD = new Set<string>();

/**
 * 알림 이력 패널(notifications row ∪ notice union 피드). 진입 시 markAllRead 로 미읽음을 해소하되,
 * 화면의 미읽음 점은 first-paint 시점의 read 상태를 스냅샷으로 캡처해 표시한다(markAllRead 후 refetch 로
 * read=true 가 돼도 이번 세션 점은 유지). 행 탭 → source 분기 딥링크(새 fetcher 없이 기존 패널 재사용).
 */
export function NotificationHistoryPanel({ open, onOpenChange }: Props) {
  const queryClient = useQueryClient();
  const [deeplink, setDeeplink] = useState<Deeplink>(null);

  // first-paint 미읽음 스냅샷 + markAllRead 1회 발화 가드. open→false 에서 리셋(재진입 시 재동작).
  const initialUnreadRef = useRef<Set<string> | null>(null);
  const markedRef = useRef(false);

  const {
    data,
    isLoading,
    isError,
    isSuccess,
    refetch,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: queryKeys.notificationsList,
    queryFn: ({ pageParam }) => notificationApi.list(pageParam),
    enabled: open,
    initialPageParam: 1,
    getNextPageParam: offsetNextPageParam,
  });

  const items = data?.pages.flatMap((p) => p.items) ?? [];

  // 렌더 중 1회 캡처 — effect 로 하면 첫 페인트에 점이 0개가 된다. open 이면서 최초 데이터 도착 시 캡처.
  if (open && initialUnreadRef.current === null && items.length > 0) {
    initialUnreadRef.current = new Set(
      items.filter((i) => !i.read).map((i) => i.id),
    );
  }
  const unreadIds = initialUnreadRef.current ?? EMPTY_UNREAD;

  // 진입 시 markAllRead → unread-count invalidate(벨/설정 점 해제). first paint 이후(성공 후) 1회.
  // open→false 시 스냅샷·발화 가드 리셋(재진입 시 신규 알림 다시 해소, stale 점 방지).
  useEffect(() => {
    if (!open) {
      markedRef.current = false;
      initialUnreadRef.current = null;
      return;
    }
    if (markedRef.current || !isSuccess) return;
    markedRef.current = true;
    // 진입 시 무조건 1회 발화. 미읽음 판정은 page 독립적인 서버 상태라 page-1 스냅샷으로 게이트하면
    // 미읽음이 2페이지 밖일 때 벨이 안 꺼진다(bug). read-all 은 멱등(204)이라 중복 발화 무해.
    notificationApi
      .markAllRead()
      .then(() =>
        queryClient.invalidateQueries({
          queryKey: queryKeys.notificationsUnread,
        }),
      )
      .catch(() => {});
  }, [open, isSuccess, queryClient]);

  const handleRowTap = (item: NotificationFeedItem) => {
    if (item.source === "notification") {
      // 개별 읽음(멱등). markAllRead 와 중복이나 계약상 유지 — 실패 무시.
      notificationApi.markRead(item.id).catch(() => {});
      if (item.ref_id && isMyPostBoardType(item.board_type)) {
        setDeeplink({
          kind: "post",
          boardType: item.board_type,
          postId: item.ref_id,
        });
      }
    } else {
      // 공지는 목록 레벨 딥링크(특정 공지까지 열지 않음 — MVP 비대칭 허용).
      setDeeplink({ kind: "notice" });
    }
  };

  return (
    <>
      <FullScreenPanel open={open} onOpenChange={onOpenChange}>
        <FullScreenPanelContent>
          <FullScreenPanelHeader title="알림" />
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
                  title="알림이 없어요"
                  description="게시판 답변·상태 변경, 새 공지가 있으면 이곳에서 알려드릴게요."
                />
              ) : (
                <>
                  <div className="rounded-2xl bg-muted/60 overflow-hidden">
                    {items.map((item) => (
                      <NotificationRow
                        key={`${item.source}-${item.id}`}
                        item={item}
                        unread={unreadIds.has(item.id)}
                        onClick={() => handleRowTap(item)}
                      />
                    ))}
                  </div>
                  <LoadMoreButton
                    hasNextPage={hasNextPage}
                    isFetchingNextPage={isFetchingNextPage}
                    onClick={() => fetchNextPage()}
                  />
                </>
              )}
            </div>
          </FullScreenPanelBody>
        </FullScreenPanelContent>
      </FullScreenPanel>

      {/* 딥링크: notification → 해당 게시판 상세(특정 글, 목록 미경유) / notice → 공지 목록.
          상세는 by-id 로 직접 열어 뒤로가기 시 목록이 아닌 이 알림 패널로 복귀한다. */}
      <MyPostDetailHost
        target={deeplink?.kind === "post" ? deeplink : null}
        onClose={() => setDeeplink(null)}
      />
      <NoticePanel
        open={deeplink?.kind === "notice"}
        onOpenChange={(o) => {
          if (!o) setDeeplink(null);
        }}
      />
    </>
  );
}

// 알림 → 게시판 상세 by-id 호스트. 목록(MyPostsListPanel)을 거치지 않고 상세를 직접 열어,
// 상세에서 뒤로가기 시 게시판 목록이 아닌 알림 패널로 복귀시킨다(NoticeDetailHost 패턴).
type PostDeeplink = Extract<Deeplink, { kind: "post" }>;

function MyPostDetailHost({
  target,
  onClose,
}: {
  target: PostDeeplink | null;
  onClose: () => void;
}) {
  // 닫힘 애니메이션 동안 payload 유지 → target 이 null 돼도 안전. 재진입마다 remountKey 로 reset.
  const { open, payload, remountKey } = useStaggeredPanel(target);
  if (payload === null) return null;
  return (
    <FullScreenPanel open={open} onOpenChange={onClose}>
      <FullScreenPanelContent key={`mypost-${remountKey}`}>
        <MyPostDetailHostContent target={payload} onClose={onClose} />
      </FullScreenPanelContent>
    </FullScreenPanel>
  );
}

function MyPostDetailHostContent({
  target,
  onClose,
}: {
  target: PostDeeplink;
  onClose: () => void;
}) {
  const router = useRouter();
  // by-id 단건 조회 — 목록 미경유. ["my-posts"] prefix 라 상세 read 처리(myPosts invalidate)로 함께 갱신.
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.myPostDetail(target.postId),
    queryFn: () => boardApi.myPost(target.postId),
  });

  // broker_statement resolved 상세의 "지금 가져오기" CTA — 일괄등록 화면으로. MyPostsListPanel 과 동일.
  const goImport = () => {
    requestImportOpen();
    onClose();
    router.push("/records");
  };

  // 로딩 중에도 패널은 즉시 열되 헤더는 딥링크의 board_type 라벨로(데이터 도착 전 표시).
  if (isLoading) {
    return (
      <>
        <FullScreenPanelHeader title={TYPE_LABEL[target.boardType]} />
        <FullScreenPanelBody>
          <div className="px-5 pt-4 space-y-3 animate-pulse">
            <div className="h-6 w-2/3 rounded bg-muted/60" />
            <div className="h-4 w-1/3 rounded bg-muted/60" />
            <div className="mt-4 h-40 rounded-2xl bg-muted/60" />
          </div>
        </FullScreenPanelBody>
      </>
    );
  }
  if (isError || !data) {
    return (
      <>
        <FullScreenPanelHeader title={TYPE_LABEL[target.boardType]} />
        <FullScreenPanelBody>
          <ErrorState onRetry={refetch} />
        </FullScreenPanelBody>
      </>
    );
  }
  return <MyPostDetailContent post={data} onImport={goImport} />;
}

function NotificationRow({
  item,
  unread,
  onClick,
}: {
  item: NotificationFeedItem;
  unread: boolean;
  onClick: () => void;
}) {
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
              "truncate text-[15px] font-medium text-foreground",
              unread && "font-semibold",
            )}
          >
            {item.title}
          </span>
          {unread ? (
            <span
              className="size-1.5 shrink-0 rounded-full bg-primary"
              aria-label="안 읽음"
            />
          ) : null}
        </span>
        {item.body ? (
          <span className="mt-0.5 block line-clamp-2 text-[13px] text-muted-foreground">
            {item.body}
          </span>
        ) : null}
        <span className="mt-1 block text-[12px] text-muted-foreground tabular-nums">
          {formatDateOnly(item.created_at)}
        </span>
      </span>
      <ChevronRightIcon className="size-5 shrink-0 text-muted-foreground" />
    </button>
  );
}
