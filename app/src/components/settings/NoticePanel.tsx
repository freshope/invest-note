"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronRightIcon, PinIcon } from "lucide-react";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  FullScreenPanelHeader,
  FullScreenPanelBody,
  useStaggeredPanel,
} from "@/components/base/FullScreenPanel";
import { EmptyCard } from "@/components/shared/EmptyCard";
import { ErrorState } from "@/components/shared/ErrorState";
import { boardApi } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { formatDateOnly } from "@/lib/format";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function NoticePanel({ open, onOpenChange }: Props) {
  // 상세로 띄울 공지 id. null 이면 상세 패널 닫힘.
  const [detailId, setDetailId] = useState<string | null>(null);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.notices,
    queryFn: () => boardApi.listNotices(),
    enabled: open,
  });

  return (
    <>
      <FullScreenPanel open={open} onOpenChange={onOpenChange}>
        <FullScreenPanelContent>
          <FullScreenPanelHeader title="공지사항" />
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
              ) : !data || data.items.length === 0 ? (
                <EmptyCard
                  title="등록된 공지가 없어요"
                  description="새로운 소식이 있으면 이곳에서 알려드릴게요."
                />
              ) : (
                <div className="rounded-2xl bg-muted/60 overflow-hidden">
                  {data.items.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setDetailId(item.id)}
                      className="flex w-full items-center justify-between gap-3 border-t border-border/60 px-5 py-4 text-left transition-colors first:border-t-0 hover:bg-foreground/5"
                    >
                      <span className="min-w-0">
                        <span className="flex items-center gap-1.5">
                          {item.is_pinned ? (
                            <PinIcon className="size-3.5 shrink-0 text-primary" />
                          ) : null}
                          <span className="truncate text-[15px] font-medium text-foreground">
                            {item.title}
                          </span>
                        </span>
                        <span className="mt-0.5 block text-[12px] text-muted-foreground tabular-nums">
                          {formatDateOnly(item.created_at)}
                        </span>
                      </span>
                      <ChevronRightIcon className="size-5 shrink-0 text-muted-foreground" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </FullScreenPanelBody>
        </FullScreenPanelContent>
      </FullScreenPanel>

      <NoticeDetailHost
        externalId={detailId}
        onClose={() => setDetailId(null)}
      />
    </>
  );
}

interface NoticeDetailHostProps {
  externalId: string | null;
  onClose: () => void;
}

function NoticeDetailHost({ externalId, onClose }: NoticeDetailHostProps) {
  // list→detail 2단계 중첩. 매 진입마다 remountKey 로 스크롤/콘텐츠 reset.
  const { open, payload, remountKey } = useStaggeredPanel(externalId);
  if (payload === null) return null;
  return (
    <FullScreenPanel open={open} onOpenChange={onClose}>
      <FullScreenPanelContent key={`notice-${remountKey}`}>
        <NoticeDetailContent id={payload} />
      </FullScreenPanelContent>
    </FullScreenPanel>
  );
}

function NoticeDetailContent({ id }: { id: string }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.notice(id),
    queryFn: () => boardApi.getNotice(id),
  });

  return (
    <>
      <FullScreenPanelHeader title="공지사항" />
      <FullScreenPanelBody>
        {isLoading ? (
          <div className="px-5 pt-4 space-y-3 animate-pulse">
            <div className="h-6 w-2/3 rounded bg-muted/60" />
            <div className="h-4 w-1/3 rounded bg-muted/60" />
            <div className="mt-4 h-40 rounded-2xl bg-muted/60" />
          </div>
        ) : isError || !data ? (
          <ErrorState onRetry={refetch} />
        ) : (
          <article className="px-5 pt-4 pb-8 space-y-3">
            <h1 className="flex items-center gap-1.5 text-[19px] font-bold text-foreground">
              {data.is_pinned ? (
                <PinIcon className="size-4 shrink-0 text-primary" />
              ) : null}
              {data.title}
            </h1>
            <p className="text-[12px] text-muted-foreground tabular-nums">
              {formatDateOnly(data.created_at)}
            </p>
            <div className="mt-2 whitespace-pre-wrap text-[15px] leading-relaxed text-foreground/90">
              {data.body}
            </div>
          </article>
        )}
      </FullScreenPanelBody>
    </>
  );
}
