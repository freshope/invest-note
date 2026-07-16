// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ReactElement } from "react";
import { FeedbackPanel } from "../FeedbackPanel";

const submitFeedback = vi.fn();

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return {
    ...actual,
    boardApi: { ...actual.boardApi, submitFeedback: (...a: unknown[]) => submitFeedback(...a) },
  };
});

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("FeedbackPanel", () => {
  it("리렌더 커밋 전 버튼을 연타해도 mutate 는 한 번만 발사된다 (동기 ref 락)", async () => {
    // mutate 를 in-flight 로 붙잡아 isPending 커밋 전 연타를 관찰한다.
    let resolve: (v: unknown) => void = () => {};
    submitFeedback.mockReturnValue(
      new Promise((r) => {
        resolve = r;
      }),
    );

    renderWithClient(<FeedbackPanel open onOpenChange={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText("의견을 입력해주세요"), {
      target: { value: "좋은 앱이에요" },
    });

    const btn = screen.getByRole("button", { name: "보내기" }) as HTMLButtonElement;
    // 한 배치 안에서 세 번 클릭 — React 가 중간에 disabled 를 커밋하지 못하므로
    // isPending 이 stale(false) 하게 유지되는 실제 브라우저 연타를 재현한다.
    await act(async () => {
      btn.click();
      btn.click();
      btn.click();
    });

    // ref 락이 없으면 클릭 수만큼 mutate 가 발사돼 중복 의견이 쌓인다. 첫 클릭만 통과해야 한다.
    expect(submitFeedback).toHaveBeenCalledTimes(1);

    resolve({ post_id: "p1" });
    await waitFor(() => expect(submitFeedback).toHaveBeenCalledTimes(1));
  });
});
