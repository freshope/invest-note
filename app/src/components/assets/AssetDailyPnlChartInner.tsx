"use client";

import { useEffect, useMemo } from "react";
import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import type { AssetHistoryPoint } from "@/lib/api-client";
import { useChartPan } from "@/hooks/useChartPan";
import { formatTick, buildYearMarks } from "./chart-utils";

/**
 * 일별 손익 막대 차트 — value = 전일대비(자산 평가액 일간 변화, '일별 내역' 표와 동일 값).
 * 이익 빨강/손실 파랑, 0 기준선. 윈도우·스와이프 팬은 자산 차트와 동일(useChartPan).
 */
export default function AssetDailyPnlChartInner({
  series,
  onFocusChange,
}: {
  series: AssetHistoryPoint[];
  /** 가장 우측 가시점(date+손익)이 바뀔 때 통지 — 헤더가 그 점을 표시. */
  onFocusChange?: (point: AssetHistoryPoint) => void;
}) {
  const { visible, panProps } = useChartPan(series);

  // 화면에 보이는 가장 우측(최근) 점 — 헤더 표시 대상 + 화살표 마커 위치.
  const focus = visible.length ? visible[visible.length - 1] : null;
  useEffect(() => {
    if (focus) onFocusChange?.(focus);
    // focus 객체는 매 렌더 새로 만들어지므로 date/value 원시값으로 의존
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus?.date, focus?.value, onFocusChange]);

  // 보이는 구간에서 연도가 바뀌는 첫 거래일 → 연도 구분선 위치(AssetHistoryChartInner와 동일).
  const yearMarks = useMemo(() => buildYearMarks(visible), [visible]);

  // y축은 가시 구간 자동 — 0을 항상 포함해 기준선이 보이게 하고, 약간의 여백을 둔다.
  const yDomain = useMemo<[number, number]>(() => {
    let min = 0;
    let max = 0;
    for (const p of visible) {
      if (p.value < min) min = p.value;
      if (p.value > max) max = p.value;
    }
    const pad = (max - min) * 0.08 || 1;
    return [min - pad, max + pad];
  }, [visible]);

  const RISE = "var(--rise)";
  const FALL = "var(--fall)";

  return (
    // [&_*:focus]:outline-none — 클릭 시 recharts svg 포커스 테두리 제거 (AllocationTabs 패턴)
    <div {...panProps} className="[&_*:focus]:outline-none">
      <ResponsiveContainer width="100%" height={170}>
        <BarChart data={visible} margin={{ top: 8, right: 8, bottom: 4, left: 8 }}>
          <XAxis
            dataKey="date"
            tickFormatter={formatTick}
            tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
            minTickGap={32}
            tickLine={false}
            axisLine={false}
          />
          <YAxis domain={yDomain} hide />
          {yearMarks.map((m) => (
            <ReferenceLine
              key={m.date}
              x={m.date}
              stroke="var(--border)"
              strokeDasharray="3 3"
              label={{
                value: m.year,
                position: "insideTop",
                fontSize: 10,
                fill: "var(--muted-foreground)",
              }}
            />
          ))}
          {/* 0 기준선 — 이익/손실 경계 */}
          <ReferenceLine y={0} stroke="var(--border)" />
          <Bar dataKey="value" isAnimationActive={false}>
            {visible.map((p) => (
              <Cell key={p.date} fill={p.value >= 0 ? RISE : FALL} />
            ))}
          </Bar>
          {/* 포커스(헤더 표시 대상) 막대 화살표 — 막대가 얇거나 값이 0이어도 위치가 보인다.
              수익: 막대 위에서 ↓ / 손실: 막대 아래에서 ↑. 색상은 막대와 동일(rise/fall). */}
          {focus && (
            <ReferenceDot
              x={focus.date}
              y={focus.value}
              shape={(props) => {
                const { cx, cy } = props as { cx: number; cy: number };
                const isRise = focus.value >= 0;
                // 샤프트(세로선) + 화살촉(꺾쇠) — 끝점이 막대 끝 4px 옆에서 막대를 가리킨다.
                const d = isRise
                  ? `M ${cx} ${cy - 12} L ${cx} ${cy - 4} M ${cx - 3} ${cy - 7.5} L ${cx} ${cy - 4} L ${cx + 3} ${cy - 7.5}`
                  : `M ${cx} ${cy + 12} L ${cx} ${cy + 4} M ${cx - 3} ${cy + 7.5} L ${cx} ${cy + 4} L ${cx + 3} ${cy + 7.5}`;
                return (
                  <path
                    d={d}
                    stroke={isRise ? RISE : FALL}
                    strokeWidth={1.5}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    fill="none"
                  />
                );
              }}
            />
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
