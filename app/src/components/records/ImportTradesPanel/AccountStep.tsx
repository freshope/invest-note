"use client";

import { Button } from "@/components/base/Button";
import { BrokerLogo } from "@/components/base/BrokerLogo";
import { FullScreenPanelFooter } from "@/components/base/FullScreenPanel";
import { cn } from "@/lib/utils";
import { BROKER_OPTIONS, type BrokerKey } from "./brokers";

interface Props {
  /** 사용자가 고른 broker(파서) 키. */
  brokerKey: BrokerKey | null;
  onSelectBroker: (key: BrokerKey) => void;
  onNext: () => void;
  /** 지원 목록에 없는 증권사 → 거래내역서 제보 진입. */
  onReportUnsupported: () => void;
}

// broker-first 흐름의 첫 스텝 — 거래내역서를 발급한 증권사(파서)를 고른다.
// 계좌는 다음 단계 preview 의 account_hint 를 계좌번호로 매칭해 결정한다.
export function AccountStep({ brokerKey, onSelectBroker, onNext, onReportUnsupported }: Props) {
  return (
    <div className="flex flex-col min-h-full">
      <div className="flex-1 px-5 pt-2 pb-4 space-y-5">
        <p className="text-sm text-muted-foreground">
          거래내역서를 발급한 증권사를 선택하세요. 선택한 증권사 형식으로 파일을 분석합니다.
        </p>

        <div className="flex flex-col gap-2">
          {BROKER_OPTIONS.map((b) => {
            const selected = b.key === brokerKey;
            return (
              <button
                key={b.key}
                type="button"
                onClick={() => onSelectBroker(b.key)}
                className={cn(
                  "flex items-center gap-3 rounded-lg border p-3 text-left transition-colors",
                  selected && "border-primary bg-primary/5",
                  !selected && "hover:bg-accent"
                )}
              >
                <BrokerLogo broker={b.label} size={36} />
                <p className="min-w-0 flex-1 truncate text-sm font-medium">{b.label}</p>
              </button>
            );
          })}
        </div>

        <button
          type="button"
          onClick={onReportUnsupported}
          className="w-full rounded-md border border-primary/40 py-2 text-xs font-medium text-primary transition-colors hover:bg-primary/5"
        >
          찾는 증권사가 없나요? 거래내역서 제보하기
        </button>
      </div>

      <FullScreenPanelFooter>
        <Button size="xl" className="w-full" onClick={onNext} disabled={!brokerKey}>
          다음
        </Button>
      </FullScreenPanelFooter>
    </div>
  );
}
