"use client";

import { useState } from "react";
import { Button } from "@/components/base/Button";
import { BrokerStatementPanel } from "@/components/broker-statement/BrokerStatementPanel";

// 설정 독립 진입점. 일괄 등록 맥락이 없으므로 증권사는 free-text, type 은 unsupported_broker 고정.
// (해외 거래 맥락은 wizard Preview/Result 에서만 진입.)
export function BrokerStatementSection() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <div className="rounded-2xl bg-muted/60 overflow-hidden">
        <Button
          type="button"
          variant="ghost"
          className="w-full h-12 text-[15px] justify-start px-5"
          onClick={() => setOpen(true)}
        >
          거래내역서 제보
        </Button>
      </div>

      <BrokerStatementPanel
        open={open}
        onOpenChange={setOpen}
        defaultType="unsupported_broker"
        brokerSource={{ mode: "freetext" }}
      />
    </>
  );
}
