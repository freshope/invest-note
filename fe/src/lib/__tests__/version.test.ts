import { describe, expect, it } from "vitest";
import { compareVersions, isUpdateRequired } from "@/lib/version";

describe("compareVersions", () => {
  it("같은 버전은 0", () => {
    expect(compareVersions("1.1.13", "1.1.13")).toBe(0);
  });
  it("낮은 버전은 -1", () => {
    expect(compareVersions("1.1.12", "1.1.13")).toBe(-1);
    expect(compareVersions("1.0.0", "1.1.0")).toBe(-1);
    expect(compareVersions("0.9.9", "1.0.0")).toBe(-1);
  });
  it("높은 버전은 1", () => {
    expect(compareVersions("1.2.0", "1.1.13")).toBe(1);
    expect(compareVersions("2.0.0", "1.99.99")).toBe(1);
  });
  it("자릿수가 다르면 0으로 패딩", () => {
    expect(compareVersions("1.1", "1.1.0")).toBe(0);
    expect(compareVersions("1.1", "1.1.1")).toBe(-1);
    expect(compareVersions("1.1.1", "1.1")).toBe(1);
  });
});

describe("isUpdateRequired", () => {
  it("현재 < 최소 → true", () => {
    expect(isUpdateRequired("1.1.12", "1.1.13")).toBe(true);
  });
  it("현재 >= 최소 → false", () => {
    expect(isUpdateRequired("1.1.13", "1.1.13")).toBe(false);
    expect(isUpdateRequired("1.2.0", "1.1.13")).toBe(false);
  });
  it("최소 버전이 비면 강제하지 않음(no-force)", () => {
    expect(isUpdateRequired("1.1.13", "")).toBe(false);
  });
  it("현재 버전이 비면 강제하지 않음", () => {
    expect(isUpdateRequired("", "1.1.13")).toBe(false);
  });
});
