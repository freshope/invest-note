// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import type { ReactElement } from "react";
import { ImportTradesPanel } from "../ImportTradesPanel";
import type { ImportPreviewResponse, ImportCommitResponse } from "@/lib/api-client";
import type { Account } from "@/types/database";

// commit 성공 시 useQueryClient 무효화에 의존하므로 QueryClient 를 제공한다.
function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const preview = vi.fn();
const commit = vi.fn();
const updateAccount = vi.fn();
const createAccount = vi.fn();

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return {
    ...actual,
    importApi: {
      ...actual.importApi,
      preview: (...a: unknown[]) => preview(...a),
      commit: (...a: unknown[]) => commit(...a),
    },
    accountsApi: {
      ...actual.accountsApi,
      update: (...a: unknown[]) => updateAccount(...a),
      create: (...a: unknown[]) => createAccount(...a),
    },
  };
});

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/lib/analytics", () => ({ capture: vi.fn() }));

// account_number 를 지정 가능한 계좌 팩토리 — hint 자동기입 게이트(null-only write) 검증용.
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

// 두 번째 계좌 — 계좌가 1개뿐이면 account 스텝을 건너뛰므로, account 스텝/매칭 경로를 검증하려면 2개 이상.
function makeAccount2(overrides: Partial<Account> = {}): Account {
  return {
    id: "acc-2",
    user_id: "user-1",
    name: "미래 계좌",
    broker: "미래에셋",
    account_number: "222-22-222222",
    cash_balance: 0,
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    ...overrides,
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

function makeCommitResult(overrides: Partial<ImportCommitResponse> = {}): ImportCommitResponse {
  return { inserted_count: 3, merged_count: 0, skipped_count: 0, error_count: 0, errors: [], ...overrides };
}

// Radix Select/카드는 jsdom 이 미구현한 pointer capture / scrollIntoView 를 사용 → 최소 shim.
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

// broker 선택 → 다음 → 파일 선택(공통 진입).
function enterFile() {
  fireEvent.click(screen.getByText("삼성증권"));
  fireEvent.click(screen.getByRole("button", { name: "다음" }));
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  fireEvent.change(input, {
    target: {
      files: [
        new File(["x"], "내역.xlsx", {
          type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }),
      ],
    },
  });
}

describe("ImportTradesPanel — 5스텝 흐름(broker→file→account→preview→commit)", () => {
  it("다계좌: 자동매칭 카드가 기본선택되고, account 스텝 확정 시 그 계좌 id 로 scoped 재-preview", async () => {
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
      <ImportTradesPanel open onOpenChange={vi.fn()} accounts={[makeAccount(), makeAccount2()]} />,
    );

    enterFile();

    // 1차 unscoped preview 후 account 스텝. 자동매칭 배지 노출.
    expect(await screen.findByText(/일치하는 계좌를 자동으로 찾았어요/)).not.toBeNull();
    await waitFor(() => expect(preview).toHaveBeenCalledTimes(1));
    expect(preview.mock.calls[0][2]).toBeUndefined();

    // account 스텝 "다음" → acc-1 기준 scoped 재-preview.
    fireEvent.click(screen.getByRole("button", { name: "다음" }));
    await waitFor(() => expect(preview).toHaveBeenCalledTimes(2));
    expect(preview.mock.calls[1][2]).toBe("acc-1");

    // preview 스텝: oversell 경고 + 차감 라벨.
    expect(await screen.findByText(/일부 거래가 제외됩니다/)).not.toBeNull();
    expect(screen.getByRole("button", { name: /제외하고 1건 등록하기/ })).not.toBeNull();
  });

  it("계좌가 1개뿐이면 account 스텝을 건너뛰고 그 계좌로 바로 scoped preview(중복 신규계좌 회귀 방지)", async () => {
    preview.mockResolvedValueOnce(makePreview({ account_hint: "123-45-678901", new_count: 3 }));

    renderWithClient(<ImportTradesPanel open onOpenChange={vi.fn()} accounts={[makeAccount()]} />);

    enterFile();

    await waitFor(() => expect(preview).toHaveBeenCalledTimes(1));
    expect(preview.mock.calls[0][2]).toBe("acc-1");
    // account 스텝 스킵 → 바로 preview 스텝 등록 라벨.
    expect(await screen.findByRole("button", { name: /3건 등록하기/ })).not.toBeNull();
  });

  it("미매칭 기존계좌(번호 null) 선택 후 commit → account_number 를 hint 로 자동기입(null-only write)", async () => {
    // acc-1 번호 null → 자동매칭 실패. 사용자가 acc-1 선택 후 commit 시 hint 를 채운다.
    preview
      .mockResolvedValueOnce(makePreview({ account_hint: "123-45-678901" }))
      .mockResolvedValueOnce(makePreview({ account_hint: "123-45-678901", new_count: 3 }));
    commit.mockResolvedValueOnce(makeCommitResult());
    updateAccount.mockResolvedValueOnce(makeAccount({ account_number: "123-45-678901" }));

    renderWithClient(
      <ImportTradesPanel
        open
        onOpenChange={vi.fn()}
        accounts={[makeAccount({ account_number: null }), makeAccount2()]}
      />,
    );

    enterFile();

    // 매칭 실패 → 신규 카드가 기본. 삼성 계좌 카드 선택 후 다음.
    await waitFor(() => expect(preview).toHaveBeenCalledTimes(1));
    fireEvent.click(await screen.findByText("삼성 계좌"));
    fireEvent.click(screen.getByRole("button", { name: "다음" }));
    await waitFor(() => expect(preview).toHaveBeenCalledTimes(2));

    // preview 스텝 → commit.
    fireEvent.click(await screen.findByRole("button", { name: /3건 등록하기/ }));

    // 번호 null 이었으므로 hint 로 자동기입(name 동봉).
    await waitFor(() => expect(updateAccount).toHaveBeenCalledTimes(1));
    expect(updateAccount.mock.calls[0][0]).toBe("acc-1");
    expect(updateAccount.mock.calls[0][1]).toMatchObject({
      name: "삼성 계좌",
      account_number: "123-45-678901",
    });
    await waitFor(() => expect(commit).toHaveBeenCalledTimes(1));
  });

  it("이미 다른 번호 보유 계좌 선택 후 commit → 자동기입 write 안 함(오염 방지)", async () => {
    // acc-1 번호 "999-99-999999" 로 hint 와 다름 → write 금지.
    preview
      .mockResolvedValueOnce(makePreview({ account_hint: "123-45-678901" }))
      .mockResolvedValueOnce(makePreview({ account_hint: "123-45-678901", new_count: 3 }));
    commit.mockResolvedValueOnce(makeCommitResult());

    renderWithClient(
      <ImportTradesPanel
        open
        onOpenChange={vi.fn()}
        accounts={[makeAccount({ account_number: "999-99-999999" }), makeAccount2()]}
      />,
    );

    enterFile();

    await waitFor(() => expect(preview).toHaveBeenCalledTimes(1));
    fireEvent.click(await screen.findByText("삼성 계좌"));
    fireEvent.click(screen.getByRole("button", { name: "다음" }));
    await waitFor(() => expect(preview).toHaveBeenCalledTimes(2));

    fireEvent.click(await screen.findByRole("button", { name: /3건 등록하기/ }));

    await waitFor(() => expect(commit).toHaveBeenCalledTimes(1));
    expect(updateAccount).not.toHaveBeenCalled();
  });

  it("신규 등록 카드 선택 후 commit → 계좌 등록 페이지 없이 commit 시점에 자동 생성", async () => {
    // hint 가 어느 계좌와도 안 맞음 → 신규 카드가 기본. 다음 → preview(폼 미방문) → commit 시 생성.
    preview.mockResolvedValueOnce(makePreview({ account_hint: "777-77-777777", new_count: 3 }));
    createAccount.mockResolvedValueOnce(
      makeAccount({ id: "acc-new", name: "삼성증권-7777", account_number: "777-77-777777" }),
    );
    commit.mockResolvedValueOnce(makeCommitResult());

    renderWithClient(
      <ImportTradesPanel open onOpenChange={vi.fn()} accounts={[makeAccount(), makeAccount2()]} />,
    );

    enterFile();

    // 매칭 실패 → 신규 카드 기본. 신규 카드 명시 선택 후 "다음" → preview(계좌 등록 폼 없이).
    await waitFor(() => expect(preview).toHaveBeenCalledTimes(1));
    fireEvent.click(await screen.findByText("새 계좌로 등록"));
    fireEvent.click(screen.getByRole("button", { name: "다음" }));

    // 신규는 재-preview 없음(1회 유지) + preview 스텝 등록 라벨.
    const commitBtn = await screen.findByRole("button", { name: /3건 등록하기/ });
    expect(preview).toHaveBeenCalledTimes(1);

    // commit → 계좌 자동 생성(이름 fallback "{증권사}-{뒷4자리}", 번호=hint) 후 그 계좌로 등록.
    fireEvent.click(commitBtn);
    await waitFor(() => expect(createAccount).toHaveBeenCalledTimes(1));
    expect(createAccount.mock.calls[0][0]).toMatchObject({
      name: "삼성증권-7777",
      account_number: "777-77-777777",
    });
    await waitFor(() => expect(commit).toHaveBeenCalledTimes(1));
    expect(commit.mock.calls[0][1]).toBe("acc-new");
  });
});
