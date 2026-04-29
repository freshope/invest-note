import { describe, it, expect } from "vitest";
import { fmtNumberInput, formatNumberInput, formatPnL, parseNumberInput } from "../format";

describe("fmtNumberInput", () => {
  it("양수를 천단위 콤마 문자열로 반환한다", () => {
    expect(fmtNumberInput(1000)).toBe("1,000");
    expect(fmtNumberInput(1234567)).toBe("1,234,567");
  });

  it("0은 빈 문자열을 반환한다", () => {
    expect(fmtNumberInput(0)).toBe("");
  });

  it("음수는 빈 문자열을 반환한다", () => {
    expect(fmtNumberInput(-1)).toBe("");
  });

  it("null/undefined는 빈 문자열을 반환한다", () => {
    expect(fmtNumberInput(null)).toBe("");
    expect(fmtNumberInput(undefined)).toBe("");
  });

  it("소수를 처리한다", () => {
    expect(fmtNumberInput(1.5)).toBe("1.5");
  });
});

describe("formatNumberInput", () => {
  it("숫자 문자열을 천단위 콤마로 포맷한다", () => {
    expect(formatNumberInput("1000")).toBe("1,000");
    expect(formatNumberInput("1234567")).toBe("1,234,567");
  });

  it("이미 콤마가 있는 입력을 재포맷한다", () => {
    expect(formatNumberInput("1,234")).toBe("1,234");
  });

  it("소수점을 허용한다", () => {
    expect(formatNumberInput("1.5")).toBe("1.5");
    expect(formatNumberInput("1234.5")).toBe("1,234.5");
  });

  it("숫자 외 문자(기호, 공백 등)를 제거한다", () => {
    expect(formatNumberInput("abc123")).toBe("123");
    expect(formatNumberInput("₩1,000")).toBe("1,000");
  });

  it("빈 문자열은 빈 문자열을 반환한다", () => {
    expect(formatNumberInput("")).toBe("");
    expect(formatNumberInput("abc")).toBe("");
  });

  it("소수점이 여러 개인 경우 첫 번째 소수점 이후를 기준으로 처리한다", () => {
    // "1.2.3" → cleaned "1.2.3" → parts ["1","2","3"] → integer "1", decimal ".2"
    expect(formatNumberInput("1.2.3")).toBe("1.2");
  });
});

describe("parseNumberInput", () => {
  it("콤마 포맷 문자열을 숫자로 파싱한다", () => {
    expect(parseNumberInput("1,234")).toBe(1234);
    expect(parseNumberInput("1,234,567")).toBe(1234567);
  });

  it("소수를 처리한다", () => {
    expect(parseNumberInput("1.5")).toBe(1.5);
    expect(parseNumberInput("1,234.5")).toBe(1234.5);
  });

  it("빈 문자열은 0을 반환한다", () => {
    expect(parseNumberInput("")).toBe(0);
  });

  it("콤마 없는 숫자 문자열을 처리한다", () => {
    expect(parseNumberInput("1000")).toBe(1000);
  });

  it("숫자가 아닌 입력은 0을 반환한다", () => {
    expect(parseNumberInput("abc")).toBe(0);
  });
});

describe("formatPnL", () => {
  it("양수는 + 부호와 콤마 포맷, 원 접미", () => {
    expect(formatPnL(1234)).toBe("+1,234원");
    expect(formatPnL(1234567)).toBe("+1,234,567원");
  });

  it("음수는 - 부호 자동, 콤마 포맷, 원 접미", () => {
    expect(formatPnL(-1234)).toBe("-1,234원");
  });

  it("0은 부호 없이 0원", () => {
    expect(formatPnL(0)).toBe("0원");
  });

  it("소수는 round 후 포맷", () => {
    expect(formatPnL(1234.4)).toBe("+1,234원");
    expect(formatPnL(1234.5)).toBe("+1,235원");
  });

  it("round 후 0이 되는 양/음수는 0원", () => {
    expect(formatPnL(0.4)).toBe("0원");
    expect(formatPnL(-0.4)).toBe("0원");
  });
});
