// 자산추이 통화 환산 — US 종목뷰는 BE series(native USD)를 현재 환율로 KRW 통일한다.
// Phase B overlay 철학: BE 무변경, FE 에서 현재 환율로 환산(historical 아님). rate=null
// (KR 종목·계좌뷰, 또는 US 환율 미상)이면 원본 그대로 반환 — 조용한 USD-as-KRW 금지는
// 호출측(fxBlocked 분기)이 담당한다.
import type { AssetHistoryItem, AssetHistoryPoint } from "@/lib/api-client";

/** series 의 value 를 KRW 로 환산. rate=null 이면 원본. */
export function convertAssetSeries(
  series: AssetHistoryPoint[],
  rate: number | null,
): AssetHistoryPoint[] {
  if (rate == null) return series;
  return series.map((p) => ({ date: p.date, value: p.value * rate }));
}

/** 매수 원금(investedAmount)을 KRW 로 환산. rate=null 또는 amount=null 이면 그대로. */
export function convertInvestedAmount(
  amount: number | null,
  rate: number | null,
): number | null {
  if (rate == null || amount == null) return amount;
  return amount * rate;
}

/**
 * 일별 손익 시계열 — items(최신 먼저)의 change 를 날짜 오름차순 point 로 변환.
 * BE 전일대비를 그대로 쓰되 US 는 KRW 환산(rate). '일별 내역' 표와 값 일치.
 */
export function convertDailySeries(
  items: AssetHistoryItem[],
  rate: number | null,
): AssetHistoryPoint[] {
  return [...items]
    .reverse()
    .map((it) => ({ date: it.date, value: rate == null ? it.change : it.change * rate }));
}

/**
 * 일별 내역 표 행 — value(자산)·change(전일대비)는 KRW 통일. close(1주당 종가)·qty 는
 * 포트폴리오 금액이 아니라 그대로 둔다(USD 종가는 별도 표시 책임). rate=null 이면 원본.
 */
export function convertItems(
  items: AssetHistoryItem[],
  rate: number | null,
): AssetHistoryItem[] {
  if (rate == null) return items;
  return items.map((it) => ({ ...it, value: it.value * rate, change: it.change * rate }));
}
