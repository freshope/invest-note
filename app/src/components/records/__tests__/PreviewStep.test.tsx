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
    account_number: null,
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
    foreign_count: 0,
    unresolved_ticker_count: 0,
    errors: [],
    validation_errors: [],
    excluded_count: 0,
    ...overrides,
  };
}

// 계좌가 확정된 기본 상태로 렌더 (등록 버튼 라벨/활성 검증용).
function renderStep(preview: ImportPreviewResponse) {
  return render(
    <PreviewStep
      preview={preview}
      resolvedAccount={makeAccount()}
      hintMismatch={false}
      onChangeAccount={vi.fn()}
      onCommit={vi.fn()}
      onReportOverseas={vi.fn()}
      isLoading={false}
    />,
  );
}

afterEach(() => cleanup());

describe("PreviewStep", () => {
  it("정합성 오류 없으면 경고 배너 미노출, 등록 버튼 활성", () => {
    renderStep(makePreview());
    expect(screen.queryByText(/일부 거래가 제외됩니다/)).toBeNull();
    const button = screen.getByRole("button", { name: /5건 등록하기/ }) as HTMLButtonElement;
    expect(button.disabled).toBe(false);
    expect(button.textContent).not.toMatch(/제외하고/);
  });

  it("validation_errors 있어도 정상 종목 등록 가능 — 버튼 활성, 경고 배너 노출", () => {
    renderStep(
      makePreview({
        new_count: 5,
        excluded_count: 2,
        validation_errors: [
          { row_no: 0, reason: "삼성전자 2026-04-12 매도 거래에 해당하는 보유 수량이 없습니다." },
        ],
      }),
    );
    expect(screen.getByText(/일부 거래가 제외됩니다/)).not.toBeNull();
    expect(screen.getByText(/보유 수량이 없습니다/)).not.toBeNull();
    const button = screen.getByRole("button", { name: /제외하고 3건 등록하기/ }) as HTMLButtonElement;
    expect(button.disabled).toBe(false);
  });

  it("모든 row가 제외 예정이면 등록 버튼 비활성", () => {
    renderStep(
      makePreview({
        new_count: 2,
        duplicate_count: 0,
        excluded_count: 2,
        validation_errors: [
          { row_no: 0, reason: "삼성전자 2026-04-12 매도 거래에 해당하는 보유 수량이 없습니다." },
        ],
      }),
    );
    const button = screen.getByRole("button", { name: /등록하기/ }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });

  it("excluded_count 만큼 '신규 등록' 카운트 카드가 차감되고 '제외 예정' 카드에 합산된다", () => {
    const { container } = renderStep(
      makePreview({
        new_count: 7,
        duplicate_count: 1,
        error_count: 1,
        excluded_count: 3,
        validation_errors: [
          { row_no: 0, reason: "카카오 2026-04-15 매도 수량이 보유 수량을 초과합니다." },
        ],
      }),
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

  it("foreign_count > 0 이면 '해외 N건 포함(USD)' 안내 노출, 미지원 고지/제보 버튼 미노출", () => {
    renderStep(makePreview({ broker_key: "toss_pdf", broker_name: "토스증권", foreign_count: 2 }));
    expect(screen.getByText(/해외 거래 2건 포함됨\(USD\)/)).not.toBeNull();
    expect(screen.queryByText(/아직 일괄 등록을 지원하지 않습니다/)).toBeNull();
    expect(screen.queryByRole("button", { name: "해외 거래내역서 제보" })).toBeNull();
  });

  it("foreign_count === 0 + 해외 지원 브로커(toss)면 어떤 해외 고지도 미노출", () => {
    renderStep(makePreview({ broker_key: "toss_pdf", broker_name: "토스증권", foreign_count: 0 }));
    expect(screen.queryByText(/해외 거래 .*포함됨\(USD\)/)).toBeNull();
    expect(screen.queryByText(/아직 일괄 등록을 지원하지 않습니다/)).toBeNull();
  });

  it("foreign_count === 0 + 해외 미지원 브로커면 기존 미지원 고지 + 제보 버튼 노출", () => {
    renderStep(makePreview({ broker_key: "samsung_xlsx", foreign_count: 0 }));
    expect(screen.getByText(/아직 일괄 등록을 지원하지 않습니다/)).not.toBeNull();
    expect(screen.getByRole("button", { name: "해외 거래내역서 제보" })).not.toBeNull();
  });

  it("확정 계좌를 읽기전용으로 표시하고 '계좌 변경' 링크를 노출한다", () => {
    renderStep(makePreview());
    expect(screen.getByText("주식계좌")).not.toBeNull();
    expect(screen.getByRole("button", { name: "계좌 변경" })).not.toBeNull();
  });

  it("hintMismatch 면 계좌번호 불일치 경고 배너 노출", () => {
    render(
      <PreviewStep
        preview={makePreview({ account_hint: "999-99-999999" })}
        resolvedAccount={makeAccount()}
        hintMismatch
        onChangeAccount={vi.fn()}
        onCommit={vi.fn()}
        onReportOverseas={vi.fn()}
        isLoading={false}
      />,
    );
    expect(screen.getByText(/선택한 계좌의 계좌번호가 파일과 달라요/)).not.toBeNull();
  });
});
