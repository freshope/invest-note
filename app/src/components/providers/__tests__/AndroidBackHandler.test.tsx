// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, cleanup, waitFor } from "@testing-library/react";
import { AndroidBackHandler } from "../AndroidBackHandler";
import { pushBackHandler } from "@/lib/back-handler";

// ─── 모킹: platform·pathname·강제업데이트·toast·capacitor ────────────────────
const mockPlatform = vi.fn(() => "android");
vi.mock("@/lib/platform", () => ({
  getPlatform: () => mockPlatform(),
}));

const mockPathname = vi.fn(() => "/");
vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname(),
}));

const mockRequired = vi.fn<() => boolean | undefined>(() => false);
vi.mock("@/hooks/useUpdateRequired", () => ({
  useUpdateRequired: () => mockRequired(),
}));

const mockToast = vi.fn();
vi.mock("sonner", () => ({
  toast: (...args: unknown[]) => mockToast(...args),
}));

// backButton 콜백 캡처 — 테스트에서 직접 백프레스 발화.
let backCb: ((evt: { canGoBack: boolean }) => void) | null = null;
const mockExitApp = vi.fn();
vi.mock("@capacitor/app", () => ({
  App: {
    exitApp: () => mockExitApp(),
    addListener: vi.fn(async (_event: string, cb: (evt: { canGoBack: boolean }) => void) => {
      backCb = cb;
      // 언마운트된 인스턴스의 콜백이 다음 테스트로 새지 않도록 실제로 해제한다.
      return { remove: vi.fn(() => { if (backCb === cb) backCb = null; }) };
    }),
  },
}));

async function mount() {
  render(<AndroidBackHandler />);
  await waitFor(() => expect(backCb).not.toBeNull());
}

function pressBack(canGoBack = true) {
  backCb?.({ canGoBack });
}

describe("AndroidBackHandler", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    backCb = null;
    mockPlatform.mockReturnValue("android");
    mockPathname.mockReturnValue("/");
    mockRequired.mockReturnValue(false);
    document.body.innerHTML = "";
  });

  afterEach(() => {
    cleanup();
    backCb = null;
  });

  it("android 가 아니면 리스너를 등록하지 않는다", async () => {
    mockPlatform.mockReturnValue("ios");
    render(<AndroidBackHandler />);
    await Promise.resolve();
    expect(backCb).toBeNull();
  });

  it("홈에서는 canGoBack 이어도 두 번 눌러 종료한다", async () => {
    await mount();

    pressBack(true);
    expect(mockExitApp).not.toHaveBeenCalled();
    expect(mockToast).toHaveBeenCalledWith("한 번 더 누르면 종료됩니다", expect.anything());

    pressBack(true);
    expect(mockExitApp).toHaveBeenCalledTimes(1);
  });

  it("확인 시간이 지나면 다시 토스트부터 시작한다", async () => {
    await mount();
    // fake timers 는 waitFor(mount) 와 충돌하므로 Date.now 만 앞당긴다.
    const realNow = Date.now();
    const now = vi.spyOn(Date, "now").mockReturnValue(realNow);

    pressBack(true);
    now.mockReturnValue(realNow + 3000);
    pressBack(true);

    expect(mockExitApp).not.toHaveBeenCalled();
    expect(mockToast).toHaveBeenCalledTimes(2);
    now.mockRestore();
  });

  it("홈이 아니고 히스토리가 있으면 뒤로 간다", async () => {
    mockPathname.mockReturnValue("/records");
    const back = vi.spyOn(window.history, "back").mockImplementation(() => {});
    await mount();

    pressBack(true);

    expect(back).toHaveBeenCalledTimes(1);
    expect(mockExitApp).not.toHaveBeenCalled();
    expect(mockToast).not.toHaveBeenCalled();
    back.mockRestore();
  });

  it("홈이 아니어도 히스토리가 없으면 종료 확인으로 간다", async () => {
    mockPathname.mockReturnValue("/records");
    await mount();

    pressBack(false);

    expect(mockToast).toHaveBeenCalledTimes(1);
  });

  it("강제 업데이트 중에는 아무것도 하지 않는다", async () => {
    mockRequired.mockReturnValue(true);
    await mount();

    pressBack(true);

    expect(mockExitApp).not.toHaveBeenCalled();
    expect(mockToast).not.toHaveBeenCalled();
  });

  it("열린 radix 레이어가 있으면 Escape 로 닫고 끝낸다", async () => {
    const dialog = document.createElement("div");
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("data-state", "open");
    document.body.appendChild(dialog);
    const onKeydown = vi.fn();
    document.addEventListener("keydown", onKeydown);
    await mount();

    pressBack(true);

    expect(onKeydown).toHaveBeenCalledTimes(1);
    expect((onKeydown.mock.calls[0][0] as KeyboardEvent).key).toBe("Escape");
    expect(mockToast).not.toHaveBeenCalled();
    document.removeEventListener("keydown", onKeydown);
  });

  it("radix 레이어가 없으면 등록된 패널 핸들러를 닫는다", async () => {
    const closePanel = vi.fn();
    const remove = pushBackHandler(closePanel);
    await mount();

    pressBack(true);

    expect(closePanel).toHaveBeenCalledTimes(1);
    expect(mockToast).not.toHaveBeenCalled();
    remove();
  });
});
