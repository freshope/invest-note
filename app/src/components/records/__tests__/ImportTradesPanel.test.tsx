import { describe, expect, it } from "vitest";
import { getInitialSelectedAccountId } from "../ImportTradesPanel";
import type { Account } from "@/types/database";

function makeAccount(id: string, broker: string | null): Account {
  return {
    id,
    user_id: "user-1",
    name: `account-${id}`,
    broker,
    cash_balance: 0,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

describe("getInitialSelectedAccountId", () => {
  it("계좌가 없으면 빈 문자열을 반환한다", () => {
    expect(getInitialSelectedAccountId([])).toBe("");
  });

  it("일괄 등록 가능한 계좌가 정확히 1개면 해당 id 를 반환한다", () => {
    const accounts = [makeAccount("a1", "삼성증권")];
    expect(getInitialSelectedAccountId(accounts)).toBe("a1");
  });

  it("일괄 등록 가능한 계좌가 2개 이상이면 빈 문자열을 반환한다 (사용자 선택 강제)", () => {
    const accounts = [
      makeAccount("a1", "삼성증권"),
      makeAccount("a2", "토스증권"),
    ];
    expect(getInitialSelectedAccountId(accounts)).toBe("");
  });

  it("미지원 증권사 계좌만 있으면 빈 문자열을 반환한다", () => {
    const accounts = [
      makeAccount("a1", "키움증권"),
      makeAccount("a2", null),
    ];
    expect(getInitialSelectedAccountId(accounts)).toBe("");
  });

  it("미지원 + 지원 1개가 섞여 있으면 지원되는 계좌의 id 를 반환한다", () => {
    const accounts = [
      makeAccount("a1", "키움증권"),
      makeAccount("a2", "삼성증권"),
      makeAccount("a3", null),
    ];
    expect(getInitialSelectedAccountId(accounts)).toBe("a2");
  });
});
