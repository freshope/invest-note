// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AccountSelectStep, NEW_ACCOUNT_ID } from "../ImportTradesPanel/AccountSelectStep";
import type { Account } from "@/types/database";

function makeAccount(overrides: Partial<Account> = {}): Account {
  return {
    id: "acc-1",
    user_id: "user-1",
    name: "삼성 계좌",
    broker: "삼성증권",
    account_number: "123-45-678901",
    cash_balance: 0,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

afterEach(() => cleanup());

function renderStep(props: Partial<React.ComponentProps<typeof AccountSelectStep>> = {}) {
  const onSelect = vi.fn();
  const onNext = vi.fn();
  render(
    <AccountSelectStep
      accounts={[makeAccount()]}
      selectedId="acc-1"
      onSelect={onSelect}
      matchedAccountId="acc-1"
      accountHint="123-45-678901"
      computedAccountName="삼성증권 8901"
      brokerLabel="삼성증권"
      onNext={onNext}
      onBack={vi.fn()}
      isLoading={false}
      {...props}
    />,
  );
  return { onSelect, onNext };
}

describe("AccountSelectStep", () => {
  it("자동매칭 계좌에 배지, 신규 카드 제공, 카드 선택/다음 콜백", () => {
    const { onSelect, onNext } = renderStep();
    expect(screen.getByText("자동 매칭")).not.toBeNull();
    expect(screen.getByText(/일치하는 계좌를 자동으로 찾았어요/)).not.toBeNull();

    fireEvent.click(screen.getByText("새 계좌로 등록"));
    expect(onSelect).toHaveBeenCalledWith(NEW_ACCOUNT_ID);

    fireEvent.click(screen.getByRole("button", { name: "다음" }));
    expect(onNext).toHaveBeenCalled();
  });

  it("선택 계좌 번호가 hint 와 다르면 불일치 경고", () => {
    renderStep({
      accounts: [makeAccount({ account_number: "999-99-999999" })],
      matchedAccountId: null,
    });
    expect(screen.getByText(/선택한 계좌의 계좌번호가 파일과 달라요/)).not.toBeNull();
  });

  it("선택 없으면 다음 비활성", () => {
    renderStep({ selectedId: "" });
    const next = screen.getByRole("button", { name: "다음" }) as HTMLButtonElement;
    expect(next.disabled).toBe(true);
  });
});
