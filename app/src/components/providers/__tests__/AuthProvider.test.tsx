// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, cleanup } from "@testing-library/react";
import { AuthProvider, useAuth } from "../AuthProvider";

// ─── supabase 클라이언트 모킹 ────────────────────────────────────────────────
const mockUnsubscribe = vi.fn();
let mockOnAuthStateChange: (event: string, session: unknown) => void = () => {};
let mockGetSessionResolve: ((value: unknown) => void) | null = null;
let mockGetSessionReject: ((reason: unknown) => void) | null = null;

const mockSupabase = {
  auth: {
    getSession: vi.fn(
      () =>
        new Promise((resolve, reject) => {
          mockGetSessionResolve = resolve;
          mockGetSessionReject = reject;
        }),
    ),
    onAuthStateChange: vi.fn((cb: (event: string, session: unknown) => void) => {
      mockOnAuthStateChange = cb;
      return { data: { subscription: { unsubscribe: mockUnsubscribe } } };
    }),
  },
};

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => mockSupabase,
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
    mockGetSessionResolve = null;
    mockGetSessionReject = null;
    mockOnAuthStateChange = () => {};
  });

  afterEach(() => {
    cleanup();
  });

  it("초기 상태는 loading=true, user=null", () => {
    renderProvider();
    expect(screen.getByTestId("loading").textContent).toBe("loading");
    expect(screen.getByTestId("user").textContent).toBe("null");
  });

  it("getSession이 유효한 세션을 반환하면 user가 설정되고 loading=false", async () => {
    renderProvider();
    await act(async () => {
      mockGetSessionResolve?.({
        data: { session: { user: { email: "test@example.com" } } },
      });
    });
    expect(screen.getByTestId("loading").textContent).toBe("done");
    expect(screen.getByTestId("user").textContent).toBe("test@example.com");
  });

  it("getSession이 null 세션을 반환하면 user=null이고 loading=false", async () => {
    renderProvider();
    await act(async () => {
      mockGetSessionResolve?.({ data: { session: null } });
    });
    expect(screen.getByTestId("loading").textContent).toBe("done");
    expect(screen.getByTestId("user").textContent).toBe("null");
  });

  it("getSession이 실패(reject)해도 user=null, loading=false로 안전하게 처리", async () => {
    renderProvider();
    await act(async () => {
      mockGetSessionReject?.(new Error("network error"));
    });
    expect(screen.getByTestId("loading").textContent).toBe("done");
    expect(screen.getByTestId("user").textContent).toBe("null");
  });

  it("onAuthStateChange SIGNED_IN 이벤트로 user가 갱신됨", async () => {
    renderProvider();
    // getSession 완료 (null)
    await act(async () => {
      mockGetSessionResolve?.({ data: { session: null } });
    });
    // onAuthStateChange 이벤트 발생
    await act(async () => {
      mockOnAuthStateChange("SIGNED_IN", { user: { email: "oauth@example.com" } });
    });
    expect(screen.getByTestId("user").textContent).toBe("oauth@example.com");
  });

  it("onAuthStateChange SIGNED_OUT 이벤트로 user=null", async () => {
    renderProvider();
    await act(async () => {
      mockGetSessionResolve?.({
        data: { session: { user: { email: "test@example.com" } } },
      });
    });
    await act(async () => {
      mockOnAuthStateChange("SIGNED_OUT", null);
    });
    expect(screen.getByTestId("user").textContent).toBe("null");
  });

  it("언마운트 시 subscription.unsubscribe() 호출", async () => {
    const { unmount } = renderProvider();
    await act(async () => {
      mockGetSessionResolve?.({ data: { session: null } });
    });
    unmount();
    expect(mockUnsubscribe).toHaveBeenCalledOnce();
  });
});
