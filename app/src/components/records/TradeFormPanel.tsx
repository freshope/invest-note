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
  const [step, setStep] = useState<Step>("basic");
  const [tradeId, setTradeId] = useState<string>("");
  const [tradeType, setTradeType] = useState<TradeType>("BUY");
  const [tradedAt, setTradedAt] = useState<string>("");

  // 패널이 열릴 때 항상 리셋 — 빠른 재오픈 시 이전 step/tradeId가 남지 않도록.
  // React 18에서는 effect 내 setState가 자동 배칭되어 추가 렌더 없이 처리됨.
  useEffect(() => {
    if (open) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setStep("basic");
      setTradeId("");
      setTradeType("BUY");
      setTradedAt("");
    }
  }, [open]);

  const handleClose = useCallback(() => {
    onOpenChange(false);
  }, [onOpenChange]);

  // stale promise 방어: API pending 중 패널이 닫히면 응답이 와도 step 전환 차단
  const openRef = useRef(open);
  useEffect(() => { openRef.current = open; }, [open]);

  const handleTradeCreated = useCallback((id: string, type: TradeType, at: string) => {
    if (!openRef.current) return;
    setTradeId(id);
    setTradeType(type);
    setTradedAt(at);
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
          {step === "meta" && tradeType === "BUY" && (
            <TradeMetaBuyForm
              tradeId={tradeId}
              onDone={handleClose}
            />
          )}
          {step === "meta" && tradeType === "SELL" && (
            <TradeMetaSellForm
              tradeId={tradeId}
              tradedAt={tradedAt}
              onDone={handleClose}
            />
          )}
        </FullScreenPanelBody>
      </FullScreenPanelContent>
    </FullScreenPanel>
  );
}
