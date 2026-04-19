"use client";

import { useState, useCallback, useEffect } from "react";
import {
  FullScreenPanel,
  FullScreenPanelContent,
  FullScreenPanelHeader,
  FullScreenPanelBody,
  PANEL_ANIMATION_MS,
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
  meta: { BUY: "근거 입력", SELL: "회고 입력" },
};

export function TradeFormPanel({ open, onOpenChange, accounts }: TradeFormPanelProps) {
  const [step, setStep] = useState<Step>("basic");
  const [tradeId, setTradeId] = useState<string>("");
  const [tradeType, setTradeType] = useState<TradeType>("BUY");

  // 컴포넌트가 항상 마운트 상태이므로 open=false 후 폼 상태를 리셋
  useEffect(() => {
    if (!open) {
      const t = setTimeout(() => {
        setStep("basic");
        setTradeId("");
        setTradeType("BUY");
      }, PANEL_ANIMATION_MS + 20);
      return () => clearTimeout(t);
    }
  }, [open]);

  const handleClose = useCallback(() => {
    onOpenChange(false);
  }, [onOpenChange]);

  const handleTradeCreated = useCallback((id: string, type: TradeType) => {
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
          {step === "meta" && tradeType === "BUY" && (
            <TradeMetaBuyForm
              tradeId={tradeId}
              onDone={handleClose}
            />
          )}
          {step === "meta" && tradeType === "SELL" && (
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
