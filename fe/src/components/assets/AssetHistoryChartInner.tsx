"use client";

import { useEffect, useId, useMemo } from "react";
import { AreaChart, Area, XAxis, YAxis, ReferenceLine, ResponsiveContainer } from "recharts";
import type { AssetHistoryPoint } from "@/lib/api-client";
import { fmtCompact } from "@/lib/format";
import { useChartPan } from "@/hooks/useChartPan";
import { formatTick, buildYearMarks } from "./chart-utils";

/** 손익 색상 모드 — 가시 윈도우 데이터 범위와 매수 원금의 위치 관계로 결정. */
type ChartMode =
  | { kind: "neutral" } // 매수 원금 없음 → 기존 보라 단색
  | { kind: "profit" } // 전 구간 수익 → 빨강 단색
  | { kind: "loss" } // 전 구간 손실 → 파랑 단색
  | { kind: "split"; offset: number; invested: number }; // 원금 라인 기준 위 빨강/아래 파랑 분할

export default function AssetHistoryChartInner({
  series,
  investedAmount,
  onFocusChange,
}: {
  series: AssetHistoryPoint[];
  /** 현재 보유분 매수 원금 — 손익 가이드 라인 기준값. null이면 단색 폴백. */
  investedAmount?: number | null;
  /** 가장 우측 가시점(date+value)이 바뀔 때 통지 — 헤더가 그 점을 표시. */
  onFocusChange?: (point: AssetHistoryPoint) => void;
}) {
  const { visible, panProps } = useChartPan(series);

  // 화면에 보이는 가장 우측(최근) 점 — 마커 위치 + 헤더 표시 대상.
  const focus = visible.length ? visible[visible.length - 1] : null;
  const focusDate = focus?.date ?? null;
  useEffect(() => {
    if (focus) onFocusChange?.(focus);
    // focus 객체는 매 렌더 새로 만들어지므로 date/value 원시값으로 의존
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus?.date, focus?.value, onFocusChange]);

  // 보이는 구간에서 연도가 바뀌는 첫 거래일 → 연도 구분선 위치(최대 2년 팬 시 방향 표시).
  const yearMarks = useMemo(() => buildYearMarks(visible), [visible]);

  // 가시 구간 데이터 범위 — y 도메인과 손익 모드 판정의 공통 입력.
  const [dataMin, dataMax] = useMemo<[number, number]>(() => {
    if (visible.length === 0) return [0, 1];
    let min = Infinity;
    let max = -Infinity;
    for (const p of visible) {
      if (p.value < min) min = p.value;
      if (p.value > max) max = p.value;
    }
    return [min, max];
  }, [visible]);

  // y축은 가시 구간 자동 — 약간의 여백을 둔다. (매수 원금은 도메인에 반영하지 않아
  // 가이드 라인 때문에 차트 모양이 변하지 않는다.)
  const yDomain = useMemo<[number, number]>(() => {
    if (dataMin === dataMax) {
      const pad = Math.abs(dataMin) * 0.05 || 1;
      return [dataMin - pad, dataMax + pad];
    }
    const pad = (dataMax - dataMin) * 0.08;
    return [dataMin - pad, dataMax + pad];
  }, [dataMin, dataMax]);

  // 매수 원금(가이드) 값 — 없거나 0 이하이면 기존 단색 차트 폴백.
  const invested = investedAmount != null && investedAmount > 0 ? investedAmount : null;

  // 손익 색상 모드. split은 원금이 가시 데이터 범위 안일 때만 — 이때 baseValue=원금으로
  // stroke/fill bbox가 [dataMin, dataMax]로 일치해 단일 offset으로 그라데이션을 공유한다.
  const mode = useMemo<ChartMode>(() => {
    if (invested == null || visible.length === 0) return { kind: "neutral" };
    if (invested <= dataMin) return { kind: "profit" };
    if (invested >= dataMax) return { kind: "loss" };
    return { kind: "split", offset: (dataMax - invested) / (dataMax - dataMin), invested };
  }, [invested, dataMin, dataMax, visible.length]);

  // 인스턴스별 그라데이션 id — 같은 문서에 차트가 2개 이상 떠도 fill 참조가 섞이지 않게.
  const uid = useId().replace(/:/g, "");
  const areaGradientId = `assetAreaGradient-${uid}`;
  const strokeGradientId = `assetStrokeGradient-${uid}`;

  const RISE = "var(--rise)";
  const FALL = "var(--fall)";
  const NEUTRAL = "var(--chart-1)";
  // 단색 모드(neutral/profit/loss)의 라인·마커·그라데이션 색.
  const solidColor = mode.kind === "profit" ? RISE : mode.kind === "loss" ? FALL : NEUTRAL;
  const dotColor =
    mode.kind === "split" && focus
      ? focus.value >= mode.invested
        ? RISE
        : FALL
      : solidColor;

  return (
    // [&_*:focus]:outline-none — 클릭 시 recharts svg 포커스 테두리 제거 (AllocationTabs 패턴)
    <div {...panProps} className="[&_*:focus]:outline-none">
      <ResponsiveContainer width="100%" height={170}>
        <AreaChart data={visible} margin={{ top: 8, right: 8, bottom: 4, left: 8 }}>
          <defs>
            {mode.kind === "split" ? (
              <>
                {/* fill: 매수 원금 라인 방향으로 양쪽 모두 fade — 위 수익(빨강)/아래 손실(파랑) */}
                <linearGradient id={areaGradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={RISE} stopOpacity={0.28} />
                  <stop offset={`${mode.offset * 100}%`} stopColor={RISE} stopOpacity={0} />
                  <stop offset={`${mode.offset * 100}%`} stopColor={FALL} stopOpacity={0} />
                  <stop offset="100%" stopColor={FALL} stopOpacity={0.28} />
                </linearGradient>
                {/* stroke: 매수 원금 라인에서 색 전환(hard stop) */}
                <linearGradient id={strokeGradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset={`${mode.offset * 100}%`} stopColor={RISE} />
                  <stop offset={`${mode.offset * 100}%`} stopColor={FALL} />
                </linearGradient>
              </>
            ) : mode.kind === "loss" ? (
              /* 손실 단색: 매수 원금이 위에 있으므로 곡선 위로 채움 — 위로 갈수록 투명 */
              <linearGradient id={areaGradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={FALL} stopOpacity={0} />
                <stop offset="100%" stopColor={FALL} stopOpacity={0.28} />
              </linearGradient>
            ) : (
              /* 수익/중립 단색: 라인 아래 세로 그라데이션 — 위쪽 진하고 아래로 투명 */
              <linearGradient id={areaGradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={solidColor} stopOpacity={0.28} />
                <stop offset="100%" stopColor={solidColor} stopOpacity={0} />
              </linearGradient>
            )}
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
          {/* 매수 원금 가이드 — 가시 데이터 범위 안일 때만(차트 모양 불변). */}
          {mode.kind === "split" && (
            <ReferenceLine
              y={mode.invested}
              stroke="var(--muted-foreground)"
              strokeDasharray="4 4"
              strokeOpacity={0.55}
              label={{
                value: `매수 ${fmtCompact(mode.invested)}`,
                position: "insideBottomLeft",
                fontSize: 9,
                fill: "var(--muted-foreground)",
              }}
            />
          )}
          <Area
            type="monotone"
            dataKey="value"
            // split: 원금 라인 기준 양면 채움 / loss: 곡선 위(원금 방향)로 채움(도메인 상단까지)
            baseValue={
              mode.kind === "split"
                ? mode.invested
                : mode.kind === "loss"
                  ? yDomain[1]
                  : undefined
            }
            stroke={mode.kind === "split" ? `url(#${strokeGradientId})` : solidColor}
            strokeWidth={2}
            fill={`url(#${areaGradientId})`}
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
                  fill={dotColor}
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
