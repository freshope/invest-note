"use client";

import { useMemo, useRef, useState, type PointerEvent } from "react";

/** 한 화면 가시 윈도우 ≈ 3개월(거래일). BE 가 series 를 최대 2년으로 캡하므로 팬 한계 = 배열 경계. */
const WINDOW = 63;
/** 한 윈도우 너비를 픽셀로 나눠 스와이프 1포인트 이동에 필요한 거리 산정 */
const SWIPE_STEP_PX = 6;

/**
 * 시계열 차트 공용 팬(가로 스와이프) 훅 — 자산 추이 Area/일별 손익 Bar 차트가 공유.
 * 윈도우 끝 인덱스를 상태로 들고, 포인터 드래그를 인덱스 이동으로 변환한다.
 * touchAction: pan-y → 가로 스와이프는 차트 팬, 세로는 페이지 스크롤 유지.
 */
export function useChartPan<T>(series: T[]) {
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

  /** 팬 영역 컨테이너에 spread 할 핸들러/스타일 묶음 */
  const panProps = {
    style: { touchAction: "pan-y" } as const,
    onPointerDown: (e: PointerEvent<HTMLElement>) => {
      dragRef.current = { startX: e.clientX, startEnd: clampedEnd };
      (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
    },
    onPointerMove: (e: PointerEvent<HTMLElement>) => {
      if (!dragRef.current) return;
      move(e.clientX - dragRef.current.startX);
    },
    onPointerUp: () => {
      dragRef.current = null;
    },
    onPointerCancel: () => {
      dragRef.current = null;
    },
  };

  return { visible, panProps };
}
