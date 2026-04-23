// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, act, cleanup } from "@testing-library/react";
import AuthCallbackPage from "../page";

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

// ─── 테스트 ──────────────────────────────────────────────────────────────────
describe("AuthCallbackPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUser = null;
    mockLoading = true;
  });

  afterEach(() => {
    cleanup();
  });

  it("loading=true일 때 스피너를 렌더하고 redirect 없음", () => {
    mockLoading = true;
    render(<AuthCallbackPage />);
    const spinner = document.querySelector(".animate-spin");
    expect(spinner).not.toBeNull();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("loading=false, user 존재 시 '/'로 redirect", async () => {
    mockLoading = false;
    mockUser = { email: "user@example.com" };
    await act(async () => {
      render(<AuthCallbackPage />);
    });
    expect(mockReplace).toHaveBeenCalledWith("/");
  });

  it("loading=false, user=null 시 '/login?error=oauth_failed'로 redirect", async () => {
    mockLoading = false;
    mockUser = null;
    await act(async () => {
      render(<AuthCallbackPage />);
    });
    expect(mockReplace).toHaveBeenCalledWith("/login?error=oauth_failed");
  });
});
