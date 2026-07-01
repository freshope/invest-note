// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import type { ReactElement } from "react";
import { ImportTradesPanel } from "../ImportTradesPanel";
import type { ImportPreviewResponse } from "@/lib/api-client";
import type { Account } from "@/types/database";

// commit 성공 시 useQueryClient 무효화에 의존하므로 QueryClient 를 제공한다.
function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const preview = vi.fn();

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return {
    ...actual,
    importApi: {
      ...actual.importApi,
      preview: (...a: unknown[]) => preview(...a),
    },
  };
});

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/lib/analytics", () => ({ capture: vi.fn() }));

function makeAccount(): Account {
  return {
    id: "acc-1",
    user_id: "user-1",
    name: "삼성 계좌",
    broker: "삼성증권",
    account_number: "123-45-678901",
    cash_balance: 0,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

function makePreview(overrides: Partial<ImportPreviewResponse> = {}): ImportPreviewResponse {
  return {
    staging_id: "s1",
    broker_key: "samsung_xlsx",
    broker_name: "삼성증권",
    account_hint: null,
    new_count: 3,
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

// Radix Select 는 jsdom 이 미구현한 pointer capture / scrollIntoView 를 사용 → 최소 shim.
beforeAll(() => {
  Element.prototype.hasPointerCapture = vi.fn(() => false);
  Element.prototype.setPointerCapture = vi.fn();
  Element.prototype.releasePointerCapture = vi.fn();
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ImportTradesPanel — 계좌번호 자동매칭 시 oversell 재-preview", () => {
  it("account_hint 로 자동매칭된 계좌 id 로 preview 를 재호출하고 oversell 경고를 노출한다", async () => {
    // 1차: account_id 없이 호출 — hint 로 acc-1 매칭. 2차: acc-1 기준 재-preview → oversell.
    preview
      .mockResolvedValueOnce(makePreview({ account_hint: "123-45-678901" }))
      .mockResolvedValueOnce(
        makePreview({
          account_hint: "123-45-678901",
          new_count: 3,
          excluded_count: 2,
          validation_errors: [
            { row_no: 0, reason: "삼성전자 2026-04-12 매도 거래에 해당하는 보유 수량이 없습니다." },
          ],
        }),
      );

    renderWithClient(
      <ImportTradesPanel open onOpenChange={vi.fn()} accounts={[makeAccount()]} />,
    );

    // broker 선택 → 다음
    fireEvent.click(screen.getByText("삼성증권"));
    fireEvent.click(screen.getByRole("button", { name: "다음" }));

    // 파일 선택 → preview 트리거 (FullScreenPanel 은 portal → document 기준 조회)
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["x"], "내역.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    fireEvent.change(input, { target: { files: [file] } });

    // preview 가 2회 호출되고, 2번째는 매칭된 account_id("acc-1") 로 호출되어야 한다.
    await waitFor(() => expect(preview).toHaveBeenCalledTimes(2));
    expect(preview.mock.calls[0][2]).toBeUndefined(); // 1차: account_id 없음
    expect(preview.mock.calls[1][2]).toBe("acc-1"); // 2차: 매칭 계좌 id

    // oversell 경고 복원 + 신규 카운트 차감(3 - 2 = 1) 버튼 라벨.
    expect(await screen.findByText(/일부 거래가 제외됩니다/)).not.toBeNull();
    expect(screen.getByRole("button", { name: /제외하고 1건 등록하기/ })).not.toBeNull();
  });

  it("힌트 매칭 계좌가 없으면 재-preview 하지 않고 account_id 없이 한 번만 호출한다", async () => {
    preview.mockResolvedValueOnce(makePreview({ account_hint: "999-99-999999" }));

    renderWithClient(
      <ImportTradesPanel open onOpenChange={vi.fn()} accounts={[makeAccount()]} />,
    );

    fireEvent.click(screen.getByText("삼성증권"));
    fireEvent.click(screen.getByRole("button", { name: "다음" }));
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, {
      target: { files: [new File(["x"], "내역.xlsx")] },
    });

    // 미매칭 → 1차 preview 만. 재-preview 없음.
    await waitFor(() => expect(preview).toHaveBeenCalledTimes(1));
    expect(preview.mock.calls[0][2]).toBeUndefined();
  });

  it("사용자가 계좌를 수동 선택하면 그 account_id 로 재-preview 하고 oversell 을 갱신한다", async () => {
    // 1차: 힌트 없음(미매칭) → 재-preview 없이 계좌 Select 노출. 2차: 수동선택 시 그 계좌로.
    preview
      .mockResolvedValueOnce(makePreview({ account_hint: null }))
      .mockResolvedValueOnce(
        makePreview({
          account_hint: null,
          new_count: 3,
          excluded_count: 2,
          validation_errors: [
            { row_no: 0, reason: "삼성전자 2026-04-12 매도 거래에 해당하는 보유 수량이 없습니다." },
          ],
        }),
      );

    renderWithClient(
      <ImportTradesPanel open onOpenChange={vi.fn()} accounts={[makeAccount()]} />,
    );

    fireEvent.click(screen.getByText("삼성증권"));
    fireEvent.click(screen.getByRole("button", { name: "다음" }));
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(["x"], "내역.xlsx")] } });

    // 1차 preview 도착 → 계좌 Select 노출(미매칭). 아직 재-preview 없음.
    await waitFor(() => expect(preview).toHaveBeenCalledTimes(1));

    // 계좌 Select 열고 항목 선택 → handleSelectAccount → 그 id 로 재-preview.
    fireEvent.click(screen.getByRole("combobox"));
    fireEvent.click(await screen.findByRole("option", { name: /삼성 계좌/ }));

    await waitFor(() => expect(preview).toHaveBeenCalledTimes(2));
    expect(preview.mock.calls[1][2]).toBe("acc-1");
    expect(await screen.findByText(/일부 거래가 제외됩니다/)).not.toBeNull();
  });
});
