// @vitest-environment jsdom
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ErrorState } from "../ErrorState";

afterEach(cleanup);

describe("ErrorState", () => {
  // 회귀: fetchQuery 기반 refetch 는 오프라인 시 promise 를 reject 한다. 예전엔 onClick 이
  // 반환값을 버려 unhandledrejection("Failed to fetch")로 표면화됐다(PostHog 예외추적 관측).
  // ErrorState 는 onRetry 반환 promise 에 rejection 핸들러를 붙여 누출을 막아야 한다.
  it("onRetry 가 반환한 reject promise 에 catch 를 붙여 unhandled 로 새지 않게 한다", () => {
    // native promise → Promise.resolve(promise) === promise, 즉 ErrorState 의 .catch 가 이 객체에 걸린다.
    const promise = Promise.reject(new TypeError("Failed to fetch"));
    const catchSpy = vi.spyOn(promise, "catch");
    const onRetry = vi.fn(() => promise);

    render(<ErrorState onRetry={onRetry} />);
    // 동기 throw 없이 클릭 처리 + onRetry 동기 호출.
    expect(() =>
      fireEvent.click(screen.getByRole("button", { name: "다시 시도" })),
    ).not.toThrow();

    expect(onRetry).toHaveBeenCalledTimes(1);
    // 핵심 회귀 가드: 반환 promise 의 rejection 이 흡수됐다(핸들러 부착).
    expect(catchSpy).toHaveBeenCalled();
  });

  it("onRetry 미제공 시 재시도 버튼을 렌더하지 않는다", () => {
    render(<ErrorState />);
    expect(screen.queryByRole("button", { name: "다시 시도" })).toBeNull();
  });
});
