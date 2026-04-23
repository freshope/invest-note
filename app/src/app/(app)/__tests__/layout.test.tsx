// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import AppLayout from "../layout";

// ─── 의존성 모킹 ─────────────────────────────────────────────────────────────
const mockReplace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
}));

let mockUser: unknown = null;
let mockLoading = true;
vi.mock("@/components/providers/AuthProvider", () => ({
  useAuth: () => ({ user: mockUser, loading: mockLoading }),
}));

vi.mock("@/components/layout/BottomNav", () => ({
  BottomNav: () => <nav data-testid="bottom-nav" />,
}));

vi.mock("@/components/panels/DetailPanelProvider", () => ({
  DetailPanelProvider: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="panel-provider">{children}</div>
  ),
}));

// ─── 테스트 ──────────────────────────────────────────────────────────────────
describe("AppLayout AuthGuard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUser = null;
    mockLoading = true;
  });

  afterEach(() => {
    cleanup();
  });

  it("loading=true일 때 스피너를 렌더하고 redirect를 호출하지 않음", () => {
    mockLoading = true;
    mockUser = null;
    render(<AppLayout><div data-testid="child" /></AppLayout>);
    expect(document.querySelector(".animate-spin")).not.toBeNull();
    expect(screen.queryByTestId("child")).toBeNull();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("loading=false, user=null일 때 /login으로 redirect 호출", () => {
    mockLoading = false;
    mockUser = null;
    render(<AppLayout><div data-testid="child" /></AppLayout>);
    expect(mockReplace).toHaveBeenCalledWith("/login");
    // null 반환 — 자식 미렌더
    expect(screen.queryByTestId("child")).toBeNull();
  });

  it("loading=false, user 존재 시 자식 컴포넌트 렌더", () => {
    mockLoading = false;
    mockUser = { email: "user@example.com" };
    render(<AppLayout><div data-testid="child" /></AppLayout>);
    expect(screen.getByTestId("child")).not.toBeNull();
    expect(screen.getByTestId("panel-provider")).not.toBeNull();
    expect(mockReplace).not.toHaveBeenCalled();
  });
});
