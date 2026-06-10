import { describe, it, expect } from "vitest";
import {
  calcChangePercent,
  calcPercent,
  currencyForCountry,
  currencySymbol,
  fmtNumberInput,
  formatFxRate,
  formatMoney,
  formatNumberInput,
  formatPctSigned,
  formatPnL,
  formatPnLCurrency,
  formatTimeKST,
  parseNumberInput,
} from "../format";

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

describe("formatFxRate", () => {
  it("₩ 접두 + 소수 2자리로 포맷한다", () => {
    expect(formatFxRate(1350)).toBe("₩1,350.00");
    expect(formatFxRate(1234.5)).toBe("₩1,234.50");
  });
});

describe("formatTimeKST", () => {
  it("UTC ISO 시각을 KST HH:mm 으로 변환한다(디바이스 TZ 무관)", () => {
    // 07:30 UTC = 16:30 KST
    expect(formatTimeKST("2026-06-09T07:30:00+00:00")).toBe("16:30");
  });

  it("자정 경계(KST)를 올바르게 처리한다", () => {
    // 15:00 UTC = 00:00 KST(익일)
    expect(formatTimeKST("2026-06-09T15:00:00+00:00")).toBe("00:00");
  });

  it("잘못된 입력은 null 을 반환한다", () => {
    expect(formatTimeKST("")).toBeNull();
    expect(formatTimeKST("not-a-date")).toBeNull();
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

describe("formatPctSigned", () => {
  it("양수는 + 부호와 소수 2자리 + %", () => {
    expect(formatPctSigned(5.43)).toBe("+5.43%");
    expect(formatPctSigned(0.01)).toBe("+0.01%");
  });

  it("음수는 - 부호 자동, 소수 2자리 + %", () => {
    expect(formatPctSigned(-2.1)).toBe("-2.10%");
    expect(formatPctSigned(-0.01)).toBe("-0.01%");
  });

  it("0은 부호 없이 0.00%", () => {
    expect(formatPctSigned(0)).toBe("0.00%");
  });

  it("반올림 후 0이 되는 작은 음수는 -0.00%가 아닌 0.00%", () => {
    expect(formatPctSigned(-0.001)).toBe("0.00%");
    expect(formatPctSigned(0.001)).toBe("0.00%");
  });

  it("decimals 인자로 자릿수 조절", () => {
    expect(formatPctSigned(5.4321, 0)).toBe("+5%");
    expect(formatPctSigned(5.4321, 1)).toBe("+5.4%");
    expect(formatPctSigned(5.4321, 3)).toBe("+5.432%");
    expect(formatPctSigned(0, 0)).toBe("0%");
  });

  it("소수점 자릿수 초과는 반올림", () => {
    expect(formatPctSigned(1.236)).toBe("+1.24%");
    expect(formatPctSigned(1.234)).toBe("+1.23%");
    expect(formatPctSigned(-1.236)).toBe("-1.24%");
  });
});

describe("currencyForCountry", () => {
  it("US는 USD, 그 외는 KRW", () => {
    expect(currencyForCountry("US")).toBe("USD");
    expect(currencyForCountry("KR")).toBe("KRW");
    expect(currencyForCountry("OTHER")).toBe("KRW");
  });
});

describe("currencySymbol", () => {
  it("등록 통화는 기호, 미등록은 코드 그대로", () => {
    expect(currencySymbol("KRW")).toBe("₩");
    expect(currencySymbol("USD")).toBe("$");
    expect(currencySymbol("JPY")).toBe("JPY");
  });
});

describe("formatMoney", () => {
  it("KRW는 정수 + 원", () => {
    expect(formatMoney(1234, "KRW")).toBe("1,234원");
    expect(formatMoney(1234)).toBe("1,234원"); // 기본 KRW
  });

  it("USD는 $ 접두 + 소수 2자리", () => {
    expect(formatMoney(12.5, "USD")).toBe("$12.50");
    expect(formatMoney(1234, "USD")).toBe("$1,234.00");
  });
});

describe("formatPnLCurrency", () => {
  it("KRW 손익은 기존 formatPnL 과 동일 형식", () => {
    expect(formatPnLCurrency(1234, "KRW")).toBe("+1,234원");
    expect(formatPnLCurrency(-1234, "KRW")).toBe("-1,234원");
    expect(formatPnLCurrency(0, "KRW")).toBe("0원");
  });

  it("USD 손익은 부호 + $ + 소수 2자리", () => {
    expect(formatPnLCurrency(12.5, "USD")).toBe("+$12.50");
    expect(formatPnLCurrency(-12.5, "USD")).toBe("-$12.50");
    expect(formatPnLCurrency(0, "USD")).toBe("$0.00");
  });

  it("round 후 0이 되는 값은 부호 없이", () => {
    expect(formatPnLCurrency(0.4, "KRW")).toBe("0원");
    expect(formatPnLCurrency(-0.001, "USD")).toBe("$0.00");
  });
});

describe("calcPercent", () => {
  it("part/total을 정수 백분율로 반환", () => {
    expect(calcPercent(1, 4)).toBe(25);
    expect(calcPercent(2, 3)).toBe(67);
  });

  it("total이 0 이하이면 0", () => {
    expect(calcPercent(5, 0)).toBe(0);
    expect(calcPercent(5, -1)).toBe(0);
  });

  it("part가 0이면 0", () => {
    expect(calcPercent(0, 100)).toBe(0);
  });
});

describe("calcChangePercent", () => {
  it("(current - prev)/prev 백분율을 소수 2자리로 반환", () => {
    expect(calcChangePercent(110, 100)).toBe(10);
    expect(calcChangePercent(105.5, 100)).toBe(5.5);
    expect(calcChangePercent(90, 100)).toBe(-10);
  });

  it("prev가 0 이하이면 0", () => {
    expect(calcChangePercent(100, 0)).toBe(0);
    expect(calcChangePercent(100, -1)).toBe(0);
  });

  it("소수 2자리 초과는 반올림", () => {
    expect(calcChangePercent(101.236, 100)).toBe(1.24);
    expect(calcChangePercent(101.234, 100)).toBe(1.23);
  });
});
