"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AreaChart, Area, XAxis, YAxis, ReferenceLine, ResponsiveContainer } from "recharts";
import type { AssetHistoryPoint } from "@/lib/api-client";

/** 한 화면 가시 윈도우 ≈ 3개월(거래일). BE 가 series 를 최대 2년으로 캡하므로 팬 한계 = 배열 경계. */
const WINDOW = 63;
/** 한 윈도우 너비를 픽셀로 나눠 스와이프 1포인트 이동에 필요한 거리 산정 */
const SWIPE_STEP_PX = 6;

function formatTick(date: string): string {
  // "2025-06-04" → "6/4"
  const [, m, d] = date.split("-");
  return `${Number(m)}/${Number(d)}`;
}

export default function AssetHistoryChartInner({
  series,
  onFocusChange,
}: {
  series: AssetHistoryPoint[];
  /** 가장 우측 가시점(date+value)이 바뀔 때 통지 — 헤더가 그 점을 표시. */
  onFocusChange?: (point: AssetHistoryPoint) => void;
}) {
  const len = series.length;
  // 윈도우 끝 인덱스(최신=len-1 에서 시작). 스와이프로 이동.
  const [endIndex, setEndIndex] = useState(len - 1);
  const dragRef = useRef<{ startX: number; startEnd: number } | null>(null);

  // len 변경(데이터 재조회) 시 endIndex 가 범위를 벗어나면 최신으로 보정
  const clampedEnd = Math.min(Math.max(endIndex, Math.min(WINDOW - 1, len - 1)), len - 1);

  const visible = useMemo(() => {
    const end = clampedEnd + 1;
    const start = Math.max(0, end - WINDOW);
    return series.slice(start, end);
  }, [series, clampedEnd]);

  // 화면에 보이는 가장 우측(최근) 점 — 마커 위치 + 헤더 표시 대상.
  const focus = visible.length ? visible[visible.length - 1] : null;
  const focusDate = focus?.date ?? null;
  useEffect(() => {
    if (focus) onFocusChange?.(focus);
    // focus 객체는 매 렌더 새로 만들어지므로 date/value 원시값으로 의존
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus?.date, focus?.value, onFocusChange]);

  // 보이는 구간에서 연도가 바뀌는 첫 거래일 → 연도 구분선 위치(최대 2년 팬 시 방향 표시).
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

  // y축은 가시 구간 자동 — 약간의 여백을 둔다.
  const yDomain = useMemo<[number, number]>(() => {
    if (visible.length === 0) return [0, 1];
    let min = Infinity;
    let max = -Infinity;
    for (const p of visible) {
      if (p.value < min) min = p.value;
      if (p.value > max) max = p.value;
    }
    if (min === max) {
      const pad = Math.abs(min) * 0.05 || 1;
      return [min - pad, max + pad];
    }
    const pad = (max - min) * 0.08;
    return [min - pad, max + pad];
  }, [visible]);

  function move(deltaPx: number) {
    // 오른쪽 스와이프(deltaPx>0) = 과거로(endIndex 감소)
    const steps = Math.round(deltaPx / SWIPE_STEP_PX);
    if (steps === 0) return;
    setEndIndex((prev) => {
      const base = dragRef.current ? dragRef.current.startEnd : prev;
      const next = base - steps;
      return Math.min(Math.max(next, Math.min(WINDOW - 1, len - 1)), len - 1);
    });
  }

  return (
    <div
      // touchAction: pan-y → 가로 스와이프는 차트 팬, 세로는 페이지 스크롤 유지
      style={{ touchAction: "pan-y" }}
      onPointerDown={(e) => {
        dragRef.current = { startX: e.clientX, startEnd: clampedEnd };
        (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
      }}
      onPointerMove={(e) => {
        if (!dragRef.current) return;
        move(e.clientX - dragRef.current.startX);
      }}
      onPointerUp={() => {
        dragRef.current = null;
      }}
      onPointerCancel={() => {
        dragRef.current = null;
      }}
    >
      <ResponsiveContainer width="100%" height={170}>
        <AreaChart data={visible} margin={{ top: 8, right: 8, bottom: 4, left: 8 }}>
          <defs>
            {/* 라인 아래 세로 그라데이션 — 위쪽 진하고 아래로 투명 */}
            <linearGradient id="assetAreaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.28} />
              <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="date"
            tickFormatter={formatTick}
            tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
            minTickGap={32}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            domain={yDomain}
            hide
          />
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
          <Area
            type="monotone"
            dataKey="value"
            stroke="var(--chart-1)"
            strokeWidth={2}
            fill="url(#assetAreaGradient)"
            dot={(props) => {
              const { cx, cy, payload, index } = props as {
                cx?: number;
                cy?: number;
                index?: number;
                payload?: { date: string };
              };
              // 가장 우측 가시점에만 마커. 그 외 점은 빈 그룹.
              if (cx == null || cy == null || payload?.date !== focusDate) {
                return <g key={`dot-${index}`} />;
              }
              return (
                <circle
                  key={`dot-${index}`}
                  cx={cx}
                  cy={cy}
                  r={3}
                  fill="var(--chart-1)"
                />
              );
            }}
            activeDot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
