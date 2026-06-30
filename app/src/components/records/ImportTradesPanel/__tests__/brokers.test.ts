import { describe, expect, it } from "vitest";

import { BROKERS } from "@/lib/brokers";

import { BROKER_OPTIONS } from "../brokers";

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
