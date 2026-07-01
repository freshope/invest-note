import { describe, it, expect } from "vitest";
import { normalizeAccountNumber, findAccountByHint } from "../account";

type Acc = { id: string; account_number: string | null };

describe("normalizeAccountNumber", () => {
  it("null/undefined/빈 문자열은 빈 문자열", () => {
    expect(normalizeAccountNumber(null)).toBe("");
    expect(normalizeAccountNumber(undefined)).toBe("");
    expect(normalizeAccountNumber("")).toBe("");
    expect(normalizeAccountNumber("   ")).toBe("");
    expect(normalizeAccountNumber("-")).toBe("");
  });

  it("하이픈·공백 등 구분자를 제거하고 숫자만 남긴다", () => {
    expect(normalizeAccountNumber("101-01-024891")).toBe("10101024891");
    expect(normalizeAccountNumber("270-26-192214")).toBe("27026192214");
    expect(normalizeAccountNumber("584-566838640")).toBe("584566838640");
    expect(normalizeAccountNumber("7157197877-14")).toBe("715719787714");
    expect(normalizeAccountNumber(" 123 456 ")).toBe("123456");
  });

  it("동일 번호의 다른 표기는 정규화 후 동일", () => {
    expect(normalizeAccountNumber("101-01-024891")).toBe(
      normalizeAccountNumber("10101024891"),
    );
  });
});

describe("findAccountByHint", () => {
  const accounts: Acc[] = [
    { id: "a1", account_number: "101-01-024891" },
    { id: "a2", account_number: "270-26-192214" },
    { id: "a3", account_number: null },
  ];

  it("정규화 동일성으로 계좌를 찾는다 (구분자 표기 차이 흡수)", () => {
    expect(findAccountByHint(accounts, "10101024891")?.id).toBe("a1");
    expect(findAccountByHint(accounts, "270-26-192214")?.id).toBe("a2");
  });

  it("다계좌 중 정확한 계좌만 매칭", () => {
    expect(findAccountByHint(accounts, "27026192214")?.id).toBe("a2");
  });

  it("힌트가 없으면(null/빈값) 매칭하지 않는다", () => {
    expect(findAccountByHint(accounts, null)).toBeNull();
    expect(findAccountByHint(accounts, "")).toBeNull();
    expect(findAccountByHint(accounts, "-")).toBeNull();
  });

  it("★empty 오탐 방지: 힌트 없음이 account_number=null 계좌에 매칭되지 않는다", () => {
    // hint 없음 → null. null-number 계좌(a3)에 조용히 붙으면 안 됨.
    expect(findAccountByHint(accounts, null)).toBeNull();
    // hint 있으나 일치 계좌 없음 → null (null-number 계좌로 폴백 안 함)
    expect(findAccountByHint(accounts, "999-99-999999")).toBeNull();
  });
});
