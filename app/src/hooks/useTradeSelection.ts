"use client";

import { useCallback, useState } from "react";

export interface UseTradeSelectionResult {
  isSelectMode: boolean;
  selectedIds: ReadonlySet<string>;
  /** 선택 모드 진입. initialId 가 주어지면 그 id 를 선택한 상태로 시작한다. */
  enter: (initialId?: string) => void;
  /** 선택 모드 종료 + 선택 비움. */
  exit: () => void;
  /** 개별 id 토글. 선택 모드가 아니어도 안전하게 무시되지 않고 set 만 갱신한다. */
  toggle: (id: string) => void;
  /** 외부에서 필터된 id 목록으로 일괄 선택. */
  selectAll: (ids: string[]) => void;
  /** 선택만 비움 (모드는 유지). */
  clearAll: () => void;
}

/**
 * 기록 탭 다중 선택 모드 상태 관리.
 *
 * - 단일 상태 트리에서 isSelectMode + selectedIds 를 함께 관리.
 * - exit() 은 모드 종료 + 선택 비움 (재진입 시 깨끗한 상태로 시작).
 * - clearAll() 은 선택만 비움 (필터 변경 시 모드는 유지하고 선택만 초기화).
 */
export function useTradeSelection(): UseTradeSelectionResult {
  const [isSelectMode, setIsSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());

  const enter = useCallback((initialId?: string) => {
    setIsSelectMode(true);
    setSelectedIds(initialId ? new Set([initialId]) : new Set());
  }, []);

  const exit = useCallback(() => {
    setIsSelectMode(false);
    setSelectedIds(new Set());
  }, []);

  const toggle = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAll = useCallback((ids: string[]) => {
    setSelectedIds(new Set(ids));
  }, []);

  const clearAll = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  return { isSelectMode, selectedIds, enter, exit, toggle, selectAll, clearAll };
}
