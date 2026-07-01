import { describe, expect, it } from "vitest";

import { BROKERS } from "@/lib/brokers";

import { BROKER_OPTIONS, isAcceptedExtension } from "../brokers";

// findBrokerKeyByAccountBroker 는 계좌의 증권사명(BROKERS[].name)을
// BROKER_OPTIONS[].label 과 정확 일치로 매칭한다. 한쪽 표기가 바뀌면
// 매칭이 조용히 null 을 반환해 해당 증권사 일괄등록이 말없이 미지원 처리된다.
// 두 테이블의 라벨 정합을 강제해 drift 를 빌드 단계에서 잡는다.
describe("BROKER_OPTIONS ↔ BROKERS 라벨 동기화", () => {
  const brokerNames = new Set(BROKERS.map((b) => b.name));

  it.each(BROKER_OPTIONS.map((o) => o.label))(
    "BROKER_OPTIONS 라벨 '%s' 는 계좌 증권사 마스터(BROKERS)에 존재한다",
    (label) => {
      expect(brokerNames).toContain(label);
    }
  );
});

describe("isAcceptedExtension", () => {
  it("단일 확장자(.pdf) 일치/불일치", () => {
    expect(isAcceptedExtension("토스내역.pdf", ".pdf")).toBe(true);
    expect(isAcceptedExtension("삼성내역.xlsx", ".pdf")).toBe(false);
  });

  it("복수 확장자(.xlsx,.xls) 중 하나라도 일치하면 true", () => {
    expect(isAcceptedExtension("a.xlsx", ".xlsx,.xls")).toBe(true);
    expect(isAcceptedExtension("a.xls", ".xlsx,.xls")).toBe(true);
    expect(isAcceptedExtension("a.pdf", ".xlsx,.xls")).toBe(false);
  });

  it("대소문자·공백 무시", () => {
    expect(isAcceptedExtension("REPORT.PDF", ".pdf")).toBe(true);
    expect(isAcceptedExtension("a.XLS", ".xlsx, .xls")).toBe(true);
  });

  it("확장자 없는 파일명은 불일치", () => {
    expect(isAcceptedExtension("noext", ".pdf")).toBe(false);
  });
});
