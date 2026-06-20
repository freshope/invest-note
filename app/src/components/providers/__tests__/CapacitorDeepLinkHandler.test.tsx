// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, cleanup, waitFor } from "@testing-library/react";
import { CapacitorDeepLinkHandler } from "../CapacitorDeepLinkHandler";
import {
  NATIVE_URL_SCHEME,
  NATIVE_CALLBACK_HOST,
} from "@/lib/auth/oauth-config";
import { LOGIN_OAUTH_FAILED_PATH_WITH_SLASH } from "@/lib/auth/errors";

// ─── 모킹: platform·router·neutral auth·capacitor 플러그인 ───────────────────
const mockIsNative = vi.fn(() => true);
vi.mock("@/lib/platform", () => ({
  isNativePlatform: () => mockIsNative(),
}));

const mockReplace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
}));

const mockExchange = vi.fn(async (_code: string) => {});
vi.mock("@/lib/auth", () => ({
  exchangeCodeForSession: (code: string) => mockExchange(code),
}));

// appUrlOpen 콜백 캡처 — 테스트에서 직접 딥링크 발화.
let appUrlOpenCb: ((evt: { url: string }) => void) | null = null;
const mockBrowserClose = vi.fn(async () => {});
const mockGetLaunchUrl = vi.fn(async () => ({ url: null as string | null }));

vi.mock("@capacitor/app", () => ({
  App: {
    getLaunchUrl: () => mockGetLaunchUrl(),
    addListener: vi.fn(async (_event: string, cb: (evt: { url: string }) => void) => {
      appUrlOpenCb = cb;
      return { remove: vi.fn() };
    }),
  },
}));

vi.mock("@capacitor/browser", () => ({
  Browser: {
    close: () => mockBrowserClose(),
    addListener: vi.fn(async () => ({ remove: vi.fn() })),
  },
}));

const SCHEME = `${NATIVE_URL_SCHEME}://${NATIVE_CALLBACK_HOST}`;

function emitUrl(url: string) {
  appUrlOpenCb?.({ url });
}

describe("CapacitorDeepLinkHandler", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    appUrlOpenCb = null;
    mockIsNative.mockReturnValue(true);
    mockGetLaunchUrl.mockResolvedValue({ url: null });
    mockExchange.mockResolvedValue(undefined);
  });

  afterEach(() => {
    cleanup();
  });

  async function mountAndReady() {
    render(<CapacitorDeepLinkHandler />);
    // useEffect 의 async IIFE 가 addListener 를 등록할 때까지 대기.
    await waitFor(() => expect(appUrlOpenCb).not.toBeNull());
  }

  it("정상 code → exchange 후 홈으로 라우팅", async () => {
    await mountAndReady();
    emitUrl(`${SCHEME}?code=abc123`);
    await waitFor(() => expect(mockExchange).toHaveBeenCalledWith("abc123"));
    expect(mockReplace).toHaveBeenCalledWith("/");
  });

  it("code 없음 → 로그인 실패 경로로 라우팅(exchange 미호출)", async () => {
    await mountAndReady();
    emitUrl(`${SCHEME}?foo=bar`);
    await waitFor(() =>
      expect(mockReplace).toHaveBeenCalledWith(LOGIN_OAUTH_FAILED_PATH_WITH_SLASH),
    );
    expect(mockExchange).not.toHaveBeenCalled();
  });

  it("error_description 우선 → error 쿼리로 라우팅(code 있어도 우선)", async () => {
    await mountAndReady();
    emitUrl(`${SCHEME}?error_description=${encodeURIComponent("접근 거부")}&code=ignored`);
    await waitFor(() =>
      expect(mockReplace).toHaveBeenCalledWith(
        `/login/?error=${encodeURIComponent("접근 거부")}`,
      ),
    );
    expect(mockExchange).not.toHaveBeenCalled();
  });

  it("scheme/host 불일치 → 무시(라우팅·exchange 없음)", async () => {
    await mountAndReady();
    emitUrl("https://evil.example.com?code=abc");
    // 비동기 처리 여지를 준 뒤 아무 부수효과 없음 확인.
    await Promise.resolve();
    expect(mockExchange).not.toHaveBeenCalled();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("exchangeCodeForSession throw → 로그인 실패 경로로 라우팅", async () => {
    mockExchange.mockRejectedValue(new Error("PKCE mismatch"));
    await mountAndReady();
    emitUrl(`${SCHEME}?code=bad`);
    await waitFor(() =>
      expect(mockReplace).toHaveBeenCalledWith(LOGIN_OAUTH_FAILED_PATH_WITH_SLASH),
    );
  });

  it("같은 URL 재발화 → dedup, exchange 1회만(G4)", async () => {
    await mountAndReady();
    emitUrl(`${SCHEME}?code=once`);
    await waitFor(() => expect(mockExchange).toHaveBeenCalledTimes(1));
    emitUrl(`${SCHEME}?code=once`);
    await Promise.resolve();
    expect(mockExchange).toHaveBeenCalledTimes(1);
  });
});
