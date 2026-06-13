// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { VALIDATION_LIMITS } from "@/lib/constants/validation";
import { TradeFreeTextField } from "../TradeFreeTextField";

describe("TradeFreeTextField", () => {
  it("글자수와 maxLength를 표시한다", () => {
    render(
      <TradeFreeTextField
        id="buy_reason"
        label="매수 메모"
        valueLength={12}
        placeholder="입력"
      />,
    );

    expect(screen.getByText(`12/${VALIDATION_LIMITS.TRADE_FREE_TEXT_MAX}`)).toBeDefined();
    expect((screen.getByLabelText("매수 메모") as HTMLTextAreaElement).maxLength).toBe(
      VALIDATION_LIMITS.TRADE_FREE_TEXT_MAX,
    );
  });

  it("90% 이상이면 카운터를 경고색으로 표시한다", () => {
    render(
      <TradeFreeTextField
        id="sell_reason"
        label="매도 이유"
        valueLength={4500}
      />,
    );

    expect(screen.getByText(`4500/${VALIDATION_LIMITS.TRADE_FREE_TEXT_MAX}`).className).toContain(
      "text-destructive",
    );
  });
});
