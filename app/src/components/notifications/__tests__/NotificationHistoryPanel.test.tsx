// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ReactElement } from "react";
import { NotificationHistoryPanel } from "../NotificationHistoryPanel";
import type { NotificationFeedItem } from "@/lib/api-client";

// 딥링크 상세는 by-id 로 직접 연다(목록 미경유). 상세 본문은 마운트/전달 post 만 검증.
vi.mock("@/components/settings/MyPostDetailPanel", () => ({
  MyPostDetailContent: ({ post }: { post: { id: string; board_type: string } }) => (
    <div data-testid="mypost-detail">
      {post.board_type}:{post.id}
    </div>
  ),
}));
vi.mock("@/components/settings/NoticePanel", () => ({
  NoticePanel: ({ open }: { open: boolean }) =>
    open ? <div data-testid="notice-panel" /> : null,
}));
// 상세 host 의 useRouter(가져오기 CTA 라우팅) — 테스트에선 no-op push.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

const list = vi.fn();
const unreadCount = vi.fn();
const markRead = vi.fn();
const markAllRead = vi.fn();
const myPost = vi.fn();

vi.mock("@/lib/api-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api-client")>();
  return {
    ...actual,
    notificationApi: {
      list: (...a: unknown[]) => list(...a),
      unreadCount: (...a: unknown[]) => unreadCount(...a),
      markRead: (...a: unknown[]) => markRead(...a),
      markAllRead: (...a: unknown[]) => markAllRead(...a),
    },
    boardApi: { ...actual.boardApi, myPost: (...a: unknown[]) => myPost(...a) },
  };
});

function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function item(overrides: Partial<NotificationFeedItem> = {}): NotificationFeedItem {
  return {
    id: "n1",
    source: "notification",
    type: "board_reply",
    title: "답변이 등록되었어요",
    body: "문의하신 내용에 답변드립니다.",
    board_type: "feedback",
    ref_id: "p1",
    created_at: "2026-07-20T00:00:00Z",
    read: false,
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("NotificationHistoryPanel", () => {
  it("목록을 렌더하고 미읽음 항목에만 점을 표시한다", async () => {
    markAllRead.mockResolvedValue(undefined);
    list.mockResolvedValue({
      items: [
        item({ id: "n1", title: "안읽음 알림", read: false }),
        item({ id: "n2", title: "읽음 알림", read: true }),
      ],
      total: 2,
      page: 1,
    });

    renderWithClient(<NotificationHistoryPanel open onOpenChange={vi.fn()} />);

    await waitFor(() => expect(screen.getByText("안읽음 알림")).toBeTruthy());
    expect(screen.getByText("읽음 알림")).toBeTruthy();
    // 미읽음 점은 정확히 1개(read=false 항목만).
    expect(screen.getAllByLabelText("안 읽음")).toHaveLength(1);
  });

  it("진입 시 markAllRead 를 1회 호출한다", async () => {
    markAllRead.mockResolvedValue(undefined);
    list.mockResolvedValue({ items: [item()], total: 1, page: 1 });

    renderWithClient(<NotificationHistoryPanel open onOpenChange={vi.fn()} />);

    await waitFor(() => expect(markAllRead).toHaveBeenCalledTimes(1));
  });

  it("빈 목록이면 안내 문구를 표시한다", async () => {
    markAllRead.mockResolvedValue(undefined);
    list.mockResolvedValue({ items: [], total: 0, page: 1 });

    renderWithClient(<NotificationHistoryPanel open onOpenChange={vi.fn()} />);

    await waitFor(() => expect(screen.getByText("알림이 없어요")).toBeTruthy());
  });

  it("에러 시 재시도 UI 를 표시한다", async () => {
    list.mockRejectedValue(new Error("boom"));

    renderWithClient(<NotificationHistoryPanel open onOpenChange={vi.fn()} />);

    await waitFor(() => expect(screen.getByText("다시 시도")).toBeTruthy());
  });

  it("notification 행 탭 → markRead 호출 + 목록 미경유하고 by-id 상세로 직접 딥링크", async () => {
    markAllRead.mockResolvedValue(undefined);
    markRead.mockResolvedValue(undefined);
    myPost.mockResolvedValue({
      id: "p1",
      board_type: "feedback",
      title: "제목",
      body: "본문",
      status: "open",
      metadata: {},
      created_at: "2026-07-20T00:00:00Z",
      updated_at: "2026-07-20T00:00:00Z",
      comments: [],
      attachments: [],
      unread: false,
      popup_acked: true,
    });
    list.mockResolvedValue({
      items: [item({ id: "n1", board_type: "feedback", ref_id: "p1" })],
      total: 1,
      page: 1,
    });

    renderWithClient(<NotificationHistoryPanel open onOpenChange={vi.fn()} />);

    const row = await screen.findByText("답변이 등록되었어요");
    fireEvent.click(row);

    await waitFor(() => expect(markRead).toHaveBeenCalledWith("n1"));
    // 목록 패널을 거치지 않고 ref_id 로 상세를 직접 조회해 연다.
    await waitFor(() => expect(myPost).toHaveBeenCalledWith("p1"));
    const detail = await screen.findByTestId("mypost-detail");
    expect(detail.textContent).toBe("feedback:p1");
    expect(screen.queryByTestId("notice-panel")).toBeNull();
  });

  it("notice 행 탭 → 공지 패널로 딥링크(markRead 미호출)", async () => {
    markAllRead.mockResolvedValue(undefined);
    list.mockResolvedValue({
      items: [
        item({
          id: "notice-1",
          source: "notice",
          type: "notice",
          title: "새 공지사항",
          board_type: "notice",
          ref_id: "notice-1",
        }),
      ],
      total: 1,
      page: 1,
    });

    renderWithClient(<NotificationHistoryPanel open onOpenChange={vi.fn()} />);

    const row = await screen.findByText("새 공지사항");
    fireEvent.click(row);

    await waitFor(() => expect(screen.getByTestId("notice-panel")).toBeTruthy());
    expect(markRead).not.toHaveBeenCalled();
    expect(screen.queryByTestId("mypost-panel")).toBeNull();
  });
});
