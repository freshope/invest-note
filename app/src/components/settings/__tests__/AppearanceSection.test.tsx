// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act, cleanup } from "@testing-library/react";
import { ThemeProvider } from "next-themes";
import { AppearanceSection } from "../AppearanceSection";

function renderWithTheme() {
  return render(
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <AppearanceSection />
    </ThemeProvider>
  );
}

async function setup() {
  await act(async () => renderWithTheme());
}

describe("AppearanceSection", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.className = "";
  });

  afterEach(() => {
    cleanup();
  });

  it("시스템/라이트/다크 버튼을 렌더한다", async () => {
    await setup();
    expect(screen.getByRole("button", { name: "시스템" })).toBeDefined();
    expect(screen.getByRole("button", { name: "라이트" })).toBeDefined();
    expect(screen.getByRole("button", { name: "다크" })).toBeDefined();
  });

  it("라이트 클릭 시 localStorage에 light가 저장된다", async () => {
    await setup();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "라이트" }));
    });
    expect(localStorage.getItem("theme")).toBe("light");
  });

  it("다크 클릭 시 html에 dark 클래스가 추가된다", async () => {
    await setup();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "다크" }));
    });
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("같은 버튼 재클릭 시 테마가 변경되지 않는다", async () => {
    await setup();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "라이트" }));
    });
    expect(localStorage.getItem("theme")).toBe("light");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "라이트" }));
    });
    expect(localStorage.getItem("theme")).toBe("light");
  });
});
