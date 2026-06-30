/**
 * offset 페이지네이션 응답용 useInfiniteQuery getNextPageParam.
 * 누적 로드 건수가 total 미만이면 다음 page 번호, 아니면 undefined(끝).
 * BE-lag(구버전 BE 가 total/page 미반환) 시 다음 페이지 없음으로 degrade.
 */
export function offsetNextPageParam(
  lastPage: { items: unknown[]; total?: number; page?: number },
  allPages: { items: unknown[] }[],
): number | undefined {
  const loaded = allPages.reduce((sum, p) => sum + p.items.length, 0);
  return loaded < (lastPage.total ?? loaded)
    ? (lastPage.page ?? allPages.length) + 1
    : undefined;
}
