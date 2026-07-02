// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act, cleanup } from "@testing-library/react";
import { ThemeProvider } from "next-themes";
import { AppearanceSection } from "../AppearanceSection";
import { DEFAULT_THEME, THEME_ATTRIBUTE } from "@/lib/constants/theme";

function renderWithTheme() {
  return render(
    <ThemeProvider attribute={THEME_ATTRIBUTE} defaultTheme={DEFAULT_THEME} enableSystem disableTransitionOnChange>
      <AppearanceSection />
    </ThemeProvider>
  );
}

async function setup() {
  await act(async () => renderWithTheme());
}

async function openPanel() {
  await act(async () => {
    fireEvent.click(screen.getByText("테마"));
  });
}

describe("AppearanceSection", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.className = "";
  });

  afterEach(() => {
    cleanup();
  });

  it("테마 행에 현재 선택값을 표시한다", async () => {
    await setup();
    expect(screen.getByText("테마")).toBeDefined();
    // 기본 테마(system)의 라벨이 행 우측에 노출된다.
    expect(screen.getByText("시스템")).toBeDefined();
  });

  it("행을 누르면 시스템/라이트/다크 옵션 패널이 열린다", async () => {
    await setup();
    await openPanel();
    expect(screen.getByRole("button", { name: "시스템" })).toBeDefined();
    expect(screen.getByRole("button", { name: "라이트" })).toBeDefined();
    expect(screen.getByRole("button", { name: "다크" })).toBeDefined();
  });

  it("라이트 옵션 클릭 시 localStorage에 light가 저장된다", async () => {
    await setup();
    await openPanel();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "라이트" }));
    });
    expect(localStorage.getItem("theme")).toBe("light");
  });

  it("다크 옵션 클릭 시 html에 dark 클래스가 추가된다", async () => {
    await setup();
    await openPanel();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "다크" }));
    });
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });
});
