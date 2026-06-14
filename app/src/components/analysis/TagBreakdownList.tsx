"use client";

import { BreakdownList } from "./BreakdownList";

// 분석/사용자 태그 통계 공통 shape — 라벨 변환만 호출측이 달리한다.
interface TagLike {
  tag: string;
  count: number;
  winRate: number;
  sumPnL: number;
}

interface TagBreakdownListProps<T extends TagLike> {
  data: T[];
  getLabel: (item: T) => string;
  isUntagged?: (item: T) => boolean;
}

/** 분석 태그(ReasoningBreakdown)·사용자 태그(CustomTagBreakdown) 공통 본문 — 다중 태그 안내 + BreakdownList. */
export function TagBreakdownList<T extends TagLike>({
  data,
  getLabel,
  isUntagged,
}: TagBreakdownListProps<T>) {
  return (
    <>
      <p className="text-[11px] text-muted-foreground">
        한 거래가 여러 태그에 포함되어 합계가 총 실현손익과 다를 수 있습니다.
      </p>
      <BreakdownList<T>
        data={data}
        emptyMessage="매칭된 태그 데이터가 없습니다"
        getKey={(d) => d.tag}
        isUntagged={isUntagged ?? (() => false)}
        getLabel={getLabel}
        getStats={(d) => ({
          count: d.count,
          sumPnL: d.sumPnL,
          winRate: d.winRate,
          hasData: d.count > 0,
        })}
      />
    </>
  );
}
