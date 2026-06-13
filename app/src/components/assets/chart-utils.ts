/** 자산 추이(Area)·일별 손익(Bar) 차트가 공유하는 축 헬퍼. */

/** x축 틱 포맷 — "2025-06-04" → "6/4" */
export function formatTick(date: string): string {
  const [, m, d] = date.split("-");
  return `${Number(m)}/${Number(d)}`;
}

/** 보이는 구간에서 연도가 바뀌는 첫 거래일 → 연도 구분선(ReferenceLine) 위치. */
export function buildYearMarks(visible: { date: string }[]): { date: string; year: string }[] {
  const out: { date: string; year: string }[] = [];
  for (let i = 1; i < visible.length; i++) {
    const year = visible[i].date.slice(0, 4);
    if (year !== visible[i - 1].date.slice(0, 4)) {
      out.push({ date: visible[i].date, year });
    }
  }
  return out;
}
