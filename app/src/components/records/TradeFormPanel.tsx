"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  FullScreenPanelHeader,
  FullScreenPanelBody,
} from "@/components/base/FullScreenPanel";
import { TradeBasicForm } from "./TradeBasicForm";
import { TradeMetaBuyForm } from "./TradeMetaBuyForm";
import { TradeMetaSellForm } from "./TradeMetaSellForm";
import { TRADE_TYPE } from "@/lib/constants/trading";
import type { Account, TradeType } from "@/types/database";

interface TradeFormPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  accounts: Account[];
}

type Step = "basic" | "meta";

const TITLES: Record<Step, Record<TradeType, string>> = {
  basic: { BUY: "거래 등록", SELL: "거래 등록" },
  meta: { BUY: "근거 입력", SELL: "매도 정보 입력" },
};

export function TradeFormPanel({ open, onOpenChange, accounts }: TradeFormPanelProps) {
  // 매 오픈마다 부모(TradeList) 가 key 를 ++ 하여 새 인스턴스를 마운트하므로
  // useState 초기값이 곧 reset 동작이 된다. 닫는 동안에는 같은 인스턴스가 유지되어
  // FullScreenPanel 슬라이드 아웃 lifecycle 이 정상 진행된다.
  const [step, setStep] = useState<Step>("basic");
  const [tradeId, setTradeId] = useState<string>("");
  const [tradeType, setTradeType] = useState<TradeType>(TRADE_TYPE.BUY);

  const handleClose = useCallback(() => {
    onOpenChange(false);
  }, [onOpenChange]);

  // stale promise 방어: API pending 중 패널이 닫히면 응답이 와도 step 전환 차단
  const openRef = useRef(open);
  useEffect(() => { openRef.current = open; }, [open]);

  const handleTradeCreated = useCallback((id: string, type: TradeType) => {
    if (!openRef.current) return;
    setTradeId(id);
    setTradeType(type);
    setStep("meta");
  }, []);

  const title = TITLES[step][tradeType];

  return (
    <FullScreenPanel open={open} onOpenChange={handleClose}>
      <FullScreenPanelContent>
        <FullScreenPanelHeader title={title} />
        <FullScreenPanelBody>
          {step === "basic" && (
            <TradeBasicForm
              accounts={accounts}
              onTradeCreated={handleTradeCreated}
            />
          )}
          {step === "meta" && tradeType === TRADE_TYPE.BUY && (
            <TradeMetaBuyForm
              tradeId={tradeId}
              onDone={handleClose}
            />
          )}
          {step === "meta" && tradeType === TRADE_TYPE.SELL && (
            <TradeMetaSellForm
              tradeId={tradeId}
              onDone={handleClose}
            />
          )}
        </FullScreenPanelBody>
      </FullScreenPanelContent>
    </FullScreenPanel>
  );
}
