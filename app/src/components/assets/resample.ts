import type { AssetHistoryItem } from "@/lib/api-client";
import type { AssetUnit } from "@/lib/constants/asset-history";

/**
 * 날짜(YYYY-MM-DD) → 단위 버킷 키(같은 구간이면 동일 문자열, 시간순 정렬 가능).
 * - day: 날짜 그대로
 * - week: 그 주 월요일의 날짜(UTC 기준 — DST/타임존 흔들림 없이 결정적)
 * - month: YYYY-MM
 */
function periodKey(date: string, unit: AssetUnit): string {
  if (unit === "month") return date.slice(0, 7);
  if (unit === "week") {
    const d = new Date(`${date}T00:00:00Z`);
    const dow = d.getUTCDay(); // 0=일 … 6=토
    const sinceMonday = (dow + 6) % 7;
    d.setUTCDate(d.getUTCDate() - sinceMonday);
    return d.toISOString().slice(0, 10);
  }
  return date;
}

/**
 * 일별 items(최신 먼저)를 표시 단위로 리샘플. 각 구간의 **마지막 거래일** 행을 대표로 채택하고
 * (value/close/qty 는 그 날 값), change 는 구간 연속 차분으로 재계산한다.
 * 자산 차트·단위별 손익·단위별 내역이 이 결과 하나에서 파생되어 항상 동일 기준을 쓴다.
 *
 * @param items 일별 행(최신 먼저) — BE items 그대로.
 * @param unit 표시 단위.
 * @param firstBaseline 첫 구간 change 기준값(= 최초 보유분 매수 원금 KRW). 일별 첫 점과 동일 의미.
 * @returns 단위 대표 행(최신 먼저).
 */
export function resampleAssetHistory(
  items: AssetHistoryItem[],
  unit: AssetUnit,
  firstBaseline: number,
): AssetHistoryItem[] {
  // 일 단위는 이미 BE 가 준 change 그대로가 정답 — 재계산 없이 통과(단일 코드경로 유지).
  if (unit === "day" || items.length === 0) return items;

  // items 는 최신 먼저 → 각 구간 첫 등장 = 그 구간의 마지막(최신) 거래일 대표.
  const reps: AssetHistoryItem[] = [];
  const seen = new Set<string>();
  for (const it of items) {
    const key = periodKey(it.date, unit);
    if (seen.has(key)) continue;
    seen.add(key);
    reps.push(it);
  }

  // 오래된 순으로 뒤집어 change 재계산: 첫 구간은 firstBaseline, 이후는 직전 구간 대비.
  reps.reverse();
  const recomputed = reps.map((it, i) => ({
    ...it,
    change: it.value - (i === 0 ? firstBaseline : reps[i - 1].value),
  }));
  recomputed.reverse(); // 최신 먼저로 원복.
  return recomputed;
}

/** 일별 items 로부터 첫 구간 change 기준값(매수 원금)을 복원. items 는 최신 먼저. */
export function firstBaselineOf(items: AssetHistoryItem[]): number {
  if (items.length === 0) return 0;
  const oldest = items[items.length - 1]; // change = oldest.value - firstBaseline
  return oldest.value - oldest.change;
}
