/** 자산 추이 표시 단위(일/주/월). 단위가 곧 줌 — useChartPan 고정 창(63포인트)에서
 *  단위를 키우면 한 화면에 담기는 기간이 늘어난다(일≈3개월 / 주≈1.2년 / 월≈전체 2년). */
export type AssetUnit = "day" | "week" | "month";

export const DEFAULT_ASSET_UNIT: AssetUnit = "day";

export const ASSET_UNITS: { value: AssetUnit; label: string }[] = [
  { value: "day", label: "일" },
  { value: "week", label: "주" },
  { value: "month", label: "월" },
];

/** 손익 탭·내역 섹션 접두 라벨 — "일별 손익" / "주별 내역" 등. */
export const UNIT_PREFIX: Record<AssetUnit, string> = {
  day: "일별",
  week: "주별",
  month: "월별",
};

/** 내역 표의 전(前)단위 대비 컬럼 라벨. */
export const UNIT_DELTA_LABEL: Record<AssetUnit, string> = {
  day: "전일대비",
  week: "전주대비",
  month: "전월대비",
};
