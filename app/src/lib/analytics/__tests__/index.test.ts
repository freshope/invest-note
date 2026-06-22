import { beforeEach, describe, expect, it, vi } from "vitest";

const posthogMock = vi.hoisted(() => ({
  capture: vi.fn(),
  identify: vi.fn(),
  register: vi.fn(),
  reset: vi.fn(),
  unregister: vi.fn(),
}));

vi.mock("posthog-js", () => ({
  default: posthogMock,
}));

async function importAnalytics() {
  vi.resetModules();
  process.env.NEXT_PUBLIC_POSTHOG_KEY = "phc_test";
  return import("../index");
}

describe("analytics app version properties", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("queues wrapper captures until app version resolution completes", async () => {
    const { capture, registerAppVersion } = await importAnalytics();

    capture("trade_recorded", { source: "manual" });
    expect(posthogMock.capture).not.toHaveBeenCalled();

    registerAppVersion({
      app_version: "1.3.0",
      native_version: "1.3.0",
      native_build: "31",
      ready: true,
    });

    expect(posthogMock.register).toHaveBeenLastCalledWith({
      app_version: "1.3.0",
      native_version: "1.3.0",
      native_build: "31",
    });
    expect(posthogMock.capture).toHaveBeenCalledWith("trade_recorded", {
      source: "manual",
    });
  });

  it("does not unregister native properties while native version is still pending", async () => {
    const { registerAppVersion } = await importAnalytics();

    registerAppVersion({
      app_version: "1.3.0",
      native_version: "",
      native_build: null,
      ready: false,
    });

    expect(posthogMock.register).toHaveBeenCalledWith({ app_version: "1.3.0" });
    expect(posthogMock.unregister).not.toHaveBeenCalled();
  });

  it("cleans persisted native properties after version lookup resolves without native values", async () => {
    const { registerAppVersion } = await importAnalytics();

    registerAppVersion({
      app_version: "1.3.0",
      native_version: "",
      native_build: null,
      ready: true,
    });

    expect(posthogMock.unregister).toHaveBeenCalledWith("native_version");
    expect(posthogMock.unregister).toHaveBeenCalledWith("native_build");
  });

  it("re-registers latest app version properties after reset", async () => {
    const { registerAppVersion, resetUser } = await importAnalytics();

    registerAppVersion({
      app_version: "1.3.1",
      native_version: "1.3.0",
      native_build: "31",
      ready: true,
    });
    posthogMock.register.mockClear();

    resetUser();

    expect(posthogMock.reset).toHaveBeenCalledOnce();
    expect(posthogMock.register).toHaveBeenCalledWith({
      app_version: "1.3.1",
      native_version: "1.3.0",
      native_build: "31",
    });
  });
});
