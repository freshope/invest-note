"use client";

import { useCallback, useEffect, useRef } from "react";

interface UseLongPressOptions {
  onLongPress: () => void;
  /** 롱프레스로 인정되는 시간 (ms). 기본 500ms. */
  threshold?: number;
  /** 이 거리(px) 이상 포인터가 움직이면 취소 (스크롤 제스처와 충돌 방지). 기본 8px. */
  moveTolerance?: number;
}

interface UseLongPressHandlers {
  onPointerDown: (e: React.PointerEvent) => void;
  onPointerMove: (e: React.PointerEvent) => void;
  onPointerUp: (e: React.PointerEvent) => void;
  onPointerCancel: (e: React.PointerEvent) => void;
  onPointerLeave: (e: React.PointerEvent) => void;
  /**
   * 부모 onClick 에서 호출해 직전 롱프레스로 인한 click 이벤트를 1회 무시할지 판단.
   * true 면 click 을 처리하지 말 것.
   */
  shouldSuppressClick: () => boolean;
}

/**
 * 포인터 이벤트 기반 롱프레스 훅.
 *
 * - threshold(기본 500ms) 동안 포인터가 유지되면 onLongPress 호출.
 * - moveTolerance(기본 8px) 이상 이동 시 취소 — 스크롤 제스처와 충돌 방지.
 * - 롱프레스가 발생하면 바로 뒤에 따라오는 click 이벤트 1회를 부모가 무시할 수 있도록
 *   shouldSuppressClick() 플래그를 제공.
 */
export function useLongPress({
  onLongPress,
  threshold = 500,
  moveTolerance = 8,
}: UseLongPressOptions): UseLongPressHandlers {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startRef = useRef<{ x: number; y: number } | null>(null);
  const triggeredRef = useRef(false);
  // 최신 콜백 참조 보존 — 핸들러 자체는 stable.
  const onLongPressRef = useRef(onLongPress);

  useEffect(() => {
    onLongPressRef.current = onLongPress;
  }, [onLongPress]);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const clear = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    startRef.current = null;
  }, []);

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      // 멀티터치/우클릭 무시 (primary pointer 만).
      if (!e.isPrimary) return;
      triggeredRef.current = false;
      startRef.current = { x: e.clientX, y: e.clientY };
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        triggeredRef.current = true;
        timerRef.current = null;
        onLongPressRef.current();
      }, threshold);
    },
    [threshold],
  );

  const onPointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!startRef.current) return;
      const dx = e.clientX - startRef.current.x;
      const dy = e.clientY - startRef.current.y;
      if (dx * dx + dy * dy > moveTolerance * moveTolerance) {
        clear();
      }
    },
    [clear, moveTolerance],
  );

  const onPointerUp = useCallback(() => {
    clear();
  }, [clear]);

  const onPointerCancel = useCallback(() => {
    clear();
  }, [clear]);

  const onPointerLeave = useCallback(() => {
    clear();
  }, [clear]);

  const shouldSuppressClick = useCallback(() => {
    if (triggeredRef.current) {
      triggeredRef.current = false;
      return true;
    }
    return false;
  }, []);

  return {
    onPointerDown,
    onPointerMove,
    onPointerUp,
    onPointerCancel,
    onPointerLeave,
    shouldSuppressClick,
  };
}
