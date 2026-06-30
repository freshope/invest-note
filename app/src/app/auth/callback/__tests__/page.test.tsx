// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, act, cleanup, waitFor } from "@testing-library/react";
import AuthCallbackPage from "../page";
import { LOGIN_OAUTH_FAILED_PATH_WITH_SLASH } from "@/lib/auth/errors";

// ─── 의존성 모킹 ─────────────────────────────────────────────────────────────
const mockReplace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
}));

const mockExchange = vi.fn();
vi.mock("@/lib/auth", () => ({
  exchangeCodeForSession: (code: string) => mockExchange(code),
}));

function setSearch(search: string) {
  window.history.replaceState({}, "", `/auth/callback${search}`);
}

// ─── 테스트 ──────────────────────────────────────────────────────────────────
describe("AuthCallbackPage (웹 BE flow code 교환)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setSearch("");
  });
  afterEach(() => {
    cleanup();
  });

  it("code 있고 교환 성공 → '/'로 replace", async () => {
    setSearch("?code=abc");
    mockExchange.mockResolvedValue(undefined);
    await act(async () => {
      render(<AuthCallbackPage />);
    });
    expect(mockExchange).toHaveBeenCalledWith("abc");
    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/"));
  });

  it("code 있고 교환 실패 → /login 에러로 replace", async () => {
    setSearch("?code=bad");
    mockExchange.mockRejectedValue(new Error("401"));
    await act(async () => {
      render(<AuthCallbackPage />);
    });
    await waitFor(() =>
      expect(mockReplace).toHaveBeenCalledWith(LOGIN_OAUTH_FAILED_PATH_WITH_SLASH),
    );
  });

  it("code 없으면 교환 안 하고 /login 에러로 replace", async () => {
    setSearch("");
    await act(async () => {
      render(<AuthCallbackPage />);
    });
    expect(mockExchange).not.toHaveBeenCalled();
    expect(mockReplace).toHaveBeenCalledWith(LOGIN_OAUTH_FAILED_PATH_WITH_SLASH);
  });

  it("once-guard: 일회용 code 교환은 1회만 호출", async () => {
    setSearch("?code=abc");
    mockExchange.mockResolvedValue(undefined);
    await act(async () => {
      render(<AuthCallbackPage />);
    });
    expect(mockExchange).toHaveBeenCalledTimes(1);
  });
});
