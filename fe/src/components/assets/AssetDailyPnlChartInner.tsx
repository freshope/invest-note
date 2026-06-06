"use client";

import { useEffect, useMemo } from "react";
import { BarChart, Bar, Rectangle, XAxis, YAxis, ReferenceLine, ResponsiveContainer } from "recharts";
import type { AssetHistoryPoint } from "@/lib/api-client";
import { useChartPan } from "@/hooks/useChartPan";

function formatTick(date: string): string {
  // "2025-06-04" → "6/4"
  const [, m, d] = date.split("-");
  return `${Number(m)}/${Number(d)}`;
}

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

  // 화면에 보이는 가장 우측(최근) 점 — 헤더 표시 대상 + 포커스 막대 강조 기준.
  const focus = visible.length ? visible[visible.length - 1] : null;
  const focusDate = focus?.date ?? null;
  useEffect(() => {
    if (focus) onFocusChange?.(focus);
    // focus 객체는 매 렌더 새로 만들어지므로 date/value 원시값으로 의존
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus?.date, focus?.value, onFocusChange]);

  // 보이는 구간에서 연도가 바뀌는 첫 거래일 → 연도 구분선 위치(AssetHistoryChartInner와 동일).
  const yearMarks = useMemo(() => {
    const out: { date: string; year: string }[] = [];
    for (let i = 1; i < visible.length; i++) {
      const year = visible[i].date.slice(0, 4);
      if (year !== visible[i - 1].date.slice(0, 4)) {
        out.push({ date: visible[i].date, year });
      }
    }
    return out;
  }, [visible]);

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
    <div {...panProps}>
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
          <Bar
            dataKey="value"
            isAnimationActive={false}
            // 포커스(헤더 표시 대상) 막대만 폭 2배 — 중심 유지를 위해 x 를 보정해 그린다.
            shape={(props) => {
              const { x, y, width, height, payload, index } = props as {
                x: number;
                y: number;
                width: number;
                height: number;
                index?: number;
                payload: AssetHistoryPoint;
              };
              const w = payload.date === focusDate ? width * 2 : width;
              return (
                <Rectangle
                  key={`bar-${index}`}
                  x={x - (w - width) / 2}
                  y={y}
                  width={w}
                  height={height}
                  fill={payload.value >= 0 ? RISE : FALL}
                />
              );
            }}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
