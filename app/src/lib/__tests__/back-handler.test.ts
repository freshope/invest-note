import { describe, it, expect, vi } from "vitest";
import { pushBackHandler, runTopBackHandler } from "../back-handler";

describe("back-handler", () => {
  it("등록된 핸들러가 없으면 false", () => {
    expect(runTopBackHandler()).toBe(false);
  });

  it("최상위(마지막 등록) 핸들러만 실행한다", () => {
    const first = vi.fn();
    const second = vi.fn();
    const removeFirst = pushBackHandler(first);
    const removeSecond = pushBackHandler(second);

    expect(runTopBackHandler()).toBe(true);
    expect(second).toHaveBeenCalledTimes(1);
    expect(first).not.toHaveBeenCalled();

    removeSecond();
    expect(runTopBackHandler()).toBe(true);
    expect(first).toHaveBeenCalledTimes(1);

    removeFirst();
    expect(runTopBackHandler()).toBe(false);
  });

  it("중간 핸들러를 먼저 해제해도 나머지 순서가 유지된다", () => {
    const bottom = vi.fn();
    const middle = vi.fn();
    const top = vi.fn();
    const removeBottom = pushBackHandler(bottom);
    const removeMiddle = pushBackHandler(middle);
    const removeTop = pushBackHandler(top);

    removeMiddle();
    runTopBackHandler();
    expect(top).toHaveBeenCalledTimes(1);

    removeTop();
    runTopBackHandler();
    expect(middle).not.toHaveBeenCalled();
    expect(bottom).toHaveBeenCalledTimes(1);

    removeBottom();
  });
});
