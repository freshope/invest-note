// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PreviewStep } from "../ImportTradesPanel/PreviewStep";
import type { ImportPreviewResponse } from "@/lib/api-client";
import type { Account } from "@/types/database";

function makeAccount(): Account {
  return {
    id: "acc-1",
    user_id: "user-1",
    name: "주식계좌",
    broker: "삼성증권",
    cash_balance: 0,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

function makePreview(overrides: Partial<ImportPreviewResponse> = {}): ImportPreviewResponse {
  return {
    staging_id: "s1",
    broker_key: "samsung",
    broker_name: "삼성증권",
    account_hint: null,
    new_count: 5,
    duplicate_count: 0,
    error_count: 0,
    usd_skip_count: 0,
    unresolved_ticker_count: 0,
    errors: [],
    validation_errors: [],
    excluded_count: 0,
    ...overrides,
  };
}

afterEach(() => cleanup());

describe("PreviewStep", () => {
  it("정합성 오류 없으면 경고 배너 미노출, 등록 버튼 활성", () => {
    render(
      <PreviewStep
        preview={makePreview()}
        account={makeAccount()}
        onCommit={vi.fn()}
        onReportOverseas={vi.fn()}
        isLoading={false}
      />,
    );
    expect(screen.queryByText(/일부 거래가 제외됩니다/)).toBeNull();
    const button = screen.getByRole("button", { name: /5건 등록하기/ }) as HTMLButtonElement;
    expect(button.disabled).toBe(false);
    expect(button.textContent).not.toMatch(/제외하고/);
  });

  it("validation_errors 있어도 정상 종목 등록 가능 — 버튼 활성, 경고 배너 노출", () => {
    render(
      <PreviewStep
        preview={makePreview({
          new_count: 5,
          excluded_count: 2,
          validation_errors: [
            { row_no: 0, reason: "삼성전자 2026-04-12 매도 거래에 해당하는 보유 수량이 없습니다." },
          ],
        })}
        account={makeAccount()}
        onCommit={vi.fn()}
        onReportOverseas={vi.fn()}
        isLoading={false}
      />,
    );
    expect(screen.getByText(/일부 거래가 제외됩니다/)).not.toBeNull();
    expect(screen.getByText(/보유 수량이 없습니다/)).not.toBeNull();
    const button = screen.getByRole("button", { name: /제외하고 3건 등록하기/ }) as HTMLButtonElement;
    expect(button.disabled).toBe(false);
  });

  it("모든 row가 제외 예정이면 등록 버튼 비활성", () => {
    render(
      <PreviewStep
        preview={makePreview({
          new_count: 2,
          duplicate_count: 0,
          excluded_count: 2,
          validation_errors: [
            { row_no: 0, reason: "삼성전자 2026-04-12 매도 거래에 해당하는 보유 수량이 없습니다." },
          ],
        })}
        account={makeAccount()}
        onCommit={vi.fn()}
        onReportOverseas={vi.fn()}
        isLoading={false}
      />,
    );
    const button = screen.getByRole("button", { name: /등록하기/ }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });

  it("excluded_count 만큼 '신규 등록' 카운트 카드가 차감되고 '제외 예정' 카드에 합산된다", () => {
    const { container } = render(
      <PreviewStep
        preview={makePreview({
          new_count: 7,
          duplicate_count: 1,
          error_count: 1,
          excluded_count: 3,
          validation_errors: [
            { row_no: 0, reason: "카카오 2026-04-15 매도 수량이 보유 수량을 초과합니다." },
          ],
        })}
        account={makeAccount()}
        onCommit={vi.fn()}
        onReportOverseas={vi.fn()}
        isLoading={false}
      />,
    );
    // 카드 라벨로 위치 찾고 값 검증
    const labels = Array.from(container.querySelectorAll("span")).filter((el) => el.textContent === "신규 등록");
    expect(labels.length).toBe(1);
    // 같은 카드의 value span 은 앞 sibling (text-2xl)
    const valueSpan = labels[0].previousElementSibling;
    expect(valueSpan?.textContent).toBe("4"); // 7 - 3

    const excludedLabels = Array.from(container.querySelectorAll("span")).filter((el) => el.textContent === "제외 예정");
    expect(excludedLabels.length).toBe(1);
    const excludedValue = excludedLabels[0].previousElementSibling;
    expect(excludedValue?.textContent).toBe("4"); // error_count 1 + excluded_count 3
  });
});
