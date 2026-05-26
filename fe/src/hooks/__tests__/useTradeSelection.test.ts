// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useTradeSelection } from "../useTradeSelection";

describe("useTradeSelection", () => {
  it("초기 상태는 선택 모드 꺼짐 + 빈 set", () => {
    const { result } = renderHook(() => useTradeSelection());
    expect(result.current.isSelectMode).toBe(false);
    expect(result.current.selectedIds.size).toBe(0);
  });

  it("enter() 호출 시 모드 진입 + 초기 id 선택", () => {
    const { result } = renderHook(() => useTradeSelection());
    act(() => result.current.enter("t-1"));
    expect(result.current.isSelectMode).toBe(true);
    expect([...result.current.selectedIds]).toEqual(["t-1"]);
  });

  it("enter() 인자 없이 호출하면 모드만 켜고 선택은 빔", () => {
    const { result } = renderHook(() => useTradeSelection());
    act(() => result.current.enter());
    expect(result.current.isSelectMode).toBe(true);
    expect(result.current.selectedIds.size).toBe(0);
  });

  it("toggle() 은 추가/제거", () => {
    const { result } = renderHook(() => useTradeSelection());
    act(() => result.current.enter("t-1"));
    act(() => result.current.toggle("t-2"));
    expect([...result.current.selectedIds].sort()).toEqual(["t-1", "t-2"]);
    act(() => result.current.toggle("t-1"));
    expect([...result.current.selectedIds]).toEqual(["t-2"]);
  });

  it("selectAll() 은 주어진 id 만 선택 (이전 선택 덮어씀)", () => {
    const { result } = renderHook(() => useTradeSelection());
    act(() => result.current.enter("t-1"));
    act(() => result.current.selectAll(["a", "b", "c"]));
    expect([...result.current.selectedIds].sort()).toEqual(["a", "b", "c"]);
  });

  it("clearAll() 은 선택만 비우고 모드는 유지", () => {
    const { result } = renderHook(() => useTradeSelection());
    act(() => result.current.enter("t-1"));
    act(() => result.current.clearAll());
    expect(result.current.isSelectMode).toBe(true);
    expect(result.current.selectedIds.size).toBe(0);
  });

  it("exit() 은 모드 종료 + 선택 비움", () => {
    const { result } = renderHook(() => useTradeSelection());
    act(() => result.current.enter("t-1"));
    act(() => result.current.toggle("t-2"));
    act(() => result.current.exit());
    expect(result.current.isSelectMode).toBe(false);
    expect(result.current.selectedIds.size).toBe(0);
  });
});
