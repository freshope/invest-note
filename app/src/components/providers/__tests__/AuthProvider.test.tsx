// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, cleanup } from "@testing-library/react";
import { AuthProvider, useAuth } from "../AuthProvider";
import type { AuthUser } from "@/lib/auth";

// ─── neutral auth API 모킹 ───────────────────────────────────────────────────
const mockUnsubscribe = vi.fn();
let mockSubscribeCallback: (user: AuthUser | null) => void = () => {};
let mockGetUserResolve: ((value: AuthUser | null) => void) | null = null;
let mockGetUserReject: ((reason: unknown) => void) | null = null;

const mockGetUser = vi.fn(
  () =>
    new Promise<AuthUser | null>((resolve, reject) => {
      mockGetUserResolve = resolve;
      mockGetUserReject = reject;
    }),
);

const mockSubscribe = vi.fn((cb: (user: AuthUser | null) => void) => {
  mockSubscribeCallback = cb;
  return mockUnsubscribe;
});

vi.mock("@/lib/auth", () => ({
  getUser: () => mockGetUser(),
  subscribe: (cb: (user: AuthUser | null) => void) => mockSubscribe(cb),
}));

// ─── 헬퍼 ────────────────────────────────────────────────────────────────────
function TestConsumer() {
  const { user, loading } = useAuth();
  return (
    <div>
      <span data-testid="loading">{loading ? "loading" : "done"}</span>
      <span data-testid="user">{user?.email ?? "null"}</span>
    </div>
  );
}

function renderProvider() {
  return render(
    <AuthProvider>
      <TestConsumer />
    </AuthProvider>,
  );
}

// ─── 테스트 ──────────────────────────────────────────────────────────────────
describe("AuthProvider", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetUserResolve = null;
    mockGetUserReject = null;
    mockSubscribeCallback = () => {};
  });

  afterEach(() => {
    cleanup();
  });

  it("초기 상태는 loading=true, user=null", () => {
    renderProvider();
    expect(screen.getByTestId("loading").textContent).toBe("loading");
    expect(screen.getByTestId("user").textContent).toBe("null");
  });

  it("getUser가 유효한 사용자를 반환하면 user가 설정되고 loading=false", async () => {
    renderProvider();
    await act(async () => {
      mockGetUserResolve?.({ id: "u1", email: "test@example.com" });
    });
    expect(screen.getByTestId("loading").textContent).toBe("done");
    expect(screen.getByTestId("user").textContent).toBe("test@example.com");
  });

  it("getUser가 null을 반환하면 user=null이고 loading=false", async () => {
    renderProvider();
    await act(async () => {
      mockGetUserResolve?.(null);
    });
    expect(screen.getByTestId("loading").textContent).toBe("done");
    expect(screen.getByTestId("user").textContent).toBe("null");
  });

  it("getUser가 실패(reject)해도 user=null, loading=false로 안전하게 처리", async () => {
    renderProvider();
    await act(async () => {
      mockGetUserReject?.(new Error("network error"));
    });
    expect(screen.getByTestId("loading").textContent).toBe("done");
    expect(screen.getByTestId("user").textContent).toBe("null");
  });

  it("subscribe 콜백 SIGNED_IN 으로 user가 갱신됨", async () => {
    renderProvider();
    // 초기 로드 완료 (null)
    await act(async () => {
      mockGetUserResolve?.(null);
    });
    // 인증 상태 변화 발생
    await act(async () => {
      mockSubscribeCallback({ id: "u2", email: "oauth@example.com" });
    });
    expect(screen.getByTestId("user").textContent).toBe("oauth@example.com");
  });

  it("subscribe 콜백 SIGNED_OUT 으로 user=null", async () => {
    renderProvider();
    await act(async () => {
      mockGetUserResolve?.({ id: "u1", email: "test@example.com" });
    });
    await act(async () => {
      mockSubscribeCallback(null);
    });
    expect(screen.getByTestId("user").textContent).toBe("null");
  });

  it("언마운트 시 unsubscribe() 호출", async () => {
    const { unmount } = renderProvider();
    await act(async () => {
      mockGetUserResolve?.(null);
    });
    unmount();
    expect(mockUnsubscribe).toHaveBeenCalledOnce();
  });
});
