// @vitest-environment jsdom
import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ImportSourceBadge } from "../ImportSourceBadge";

afterEach(cleanup);

describe("ImportSourceBadge", () => {
  it("origin이 IMPORT면 '거래내역서' 배지를 렌더한다", () => {
    render(<ImportSourceBadge origin="IMPORT" />);
    expect(screen.queryByText("거래내역서")).not.toBeNull();
  });

  it("origin이 MANUAL이면 아무것도 렌더하지 않는다", () => {
    const { container } = render(<ImportSourceBadge origin="MANUAL" />);
    expect(container.firstChild).toBeNull();
  });
});
