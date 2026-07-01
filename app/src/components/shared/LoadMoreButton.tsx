interface Props {
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  onClick: () => void;
}

/** 무한스크롤 목록 하단 "더 보기" 버튼 (공지·내 제보 패널 공통). */
export function LoadMoreButton({
  hasNextPage,
  isFetchingNextPage,
  onClick,
}: Props) {
  if (!hasNextPage) return null;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={isFetchingNextPage}
      className="mt-3 w-full rounded-xl bg-muted/60 py-3 text-[14px] font-medium text-muted-foreground transition-colors hover:bg-foreground/5 disabled:opacity-60"
    >
      {isFetchingNextPage ? "불러오는 중…" : "더 보기"}
    </button>
  );
}
