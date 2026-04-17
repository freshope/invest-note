"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/base/Button";
import { Input } from "@/components/base/Input";
import { Label } from "@/components/base/Label";
import { Textarea } from "@/components/base/Textarea";
import { tradesApi } from "@/lib/api-client";
import type { TradeResult } from "@/types/database";
import { STRATEGIES, EMOTIONS } from "./constants";

interface TradeMetaSellFormProps {
  tradeId: string;
  onDone: () => void;
}

const RESULTS: { value: TradeResult; label: string; color: string }[] = [
  { value: "SUCCESS", label: "수익 ✅", color: "bg-[var(--rise)] text-white border-[var(--rise)]" },
  { value: "FAIL", label: "손실 ❌", color: "bg-[var(--fall)] text-white border-[var(--fall)]" },
  { value: "BREAKEVEN", label: "본전 ➖", color: "bg-muted text-foreground border-border" },
];

function formatNumber(raw: string): string {
  const cleaned = raw.replace(/[^0-9-]/g, "");
  if (!cleaned || cleaned === "-") return cleaned;
  const isNeg = cleaned.startsWith("-");
  const digits = cleaned.replace(/-/g, "");
  if (!digits) return isNeg ? "-" : "";
  return (isNeg ? "-" : "") + Number(digits).toLocaleString("ko-KR");
}

export function TradeMetaSellForm({ tradeId, onDone }: TradeMetaSellFormProps) {
  const router = useRouter();
  const [result, setResult] = useState<TradeResult | "">("");
  const [strategy, setStrategy] = useState<string>("");
  const [emotion, setEmotion] = useState<string>("");
  const [profitLossDisplay, setProfitLossDisplay] = useState("");
  const [sellReason, setSellReason] = useState("");
  const [reflectionNote, setReflectionNote] = useState("");
  const [improvementNote, setImprovementNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      const profitLossRaw = profitLossDisplay.replace(/,/g, "");
      await tradesApi.update(tradeId, {
        result: result || null,
        strategy_type: (strategy || null) as import("@/types/database").StrategyType | null,
        emotion: (emotion || null) as import("@/types/database").EmotionType | null,
        profit_loss: profitLossRaw ? Number(profitLossRaw) : null,
        sell_reason: sellReason.trim() || null,
        reflection_note: reflectionNote.trim() || null,
        improvement_note: improvementNote.trim() || null,
      });
      router.refresh();
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "오류가 발생했습니다.");
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col min-h-full">
      <div className="flex-1 px-5 pt-2 pb-4 space-y-6">
        {/* 거래 결과 */}
        <div className="space-y-2">
          <Label>거래 결과</Label>
          <div className="grid grid-cols-3 gap-2">
            {RESULTS.map((r) => (
              <button
                key={r.value}
                type="button"
                onClick={() => setResult(result === r.value ? "" : r.value)}
                className={`rounded-xl border py-3 text-[13px] font-bold transition-colors ${
                  result === r.value
                    ? r.color
                    : "border-border bg-muted/50 text-muted-foreground"
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>

        {/* 손익 금액 */}
        <div className="space-y-1.5">
          <Label htmlFor="profit_loss_input">손익 금액 (원) <span className="text-[12px] font-normal text-muted-foreground">음수=손실</span></Label>
          <Input
            id="profit_loss_input"
            type="text"
            inputMode="numeric"
            placeholder="예: 150,000 또는 -50,000"
            value={profitLossDisplay}
            onChange={(e) => setProfitLossDisplay(formatNumber(e.target.value))}
          />
        </div>

        {/* 매도 이유 */}
        <div className="space-y-1.5">
          <Label htmlFor="sell_reason">매도 이유</Label>
          <Textarea
            id="sell_reason"
            value={sellReason}
            onChange={(e) => setSellReason(e.target.value)}
            placeholder="왜 매도했나요?"
            rows={2}
          />
        </div>

        {/* 잘한 점 */}
        <div className="space-y-1.5">
          <Label htmlFor="reflection_note">잘한 점 / 배운 점</Label>
          <Textarea
            id="reflection_note"
            value={reflectionNote}
            onChange={(e) => setReflectionNote(e.target.value)}
            placeholder="이번 거래에서 잘한 점이나 배운 것을 기록해보세요"
            rows={3}
          />
        </div>

        {/* 개선할 점 */}
        <div className="space-y-1.5">
          <Label htmlFor="improvement_note">개선할 점 / 다음에는</Label>
          <Textarea
            id="improvement_note"
            value={improvementNote}
            onChange={(e) => setImprovementNote(e.target.value)}
            placeholder="다음 거래에서 개선하고 싶은 점을 적어주세요"
            rows={3}
          />
        </div>

        {/* 전략 */}
        <div className="space-y-2">
          <Label>전략</Label>
          <div className="grid grid-cols-4 gap-2">
            {STRATEGIES.map((s) => (
              <button
                key={s.value}
                type="button"
                onClick={() => setStrategy(strategy === s.value ? "" : s.value)}
                className={`rounded-xl border py-2.5 text-[13px] font-semibold transition-colors ${
                  strategy === s.value
                    ? "bg-primary text-primary-foreground border-primary"
                    : "border-border bg-muted/50 text-muted-foreground"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {/* 감정 */}
        <div className="space-y-2">
          <Label>감정</Label>
          <div className="grid grid-cols-3 gap-2">
            {EMOTIONS.map((e) => (
              <button
                key={e.value}
                type="button"
                onClick={() => setEmotion(emotion === e.value ? "" : e.value)}
                className={`rounded-xl border py-2.5 text-[13px] font-semibold transition-colors ${
                  emotion === e.value
                    ? "bg-primary text-primary-foreground border-primary"
                    : "border-border bg-muted/50 text-muted-foreground"
                }`}
              >
                {e.label}
              </button>
            ))}
          </div>
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>

      <div
        className="sticky bottom-0 bg-background px-5 pt-3 pb-4 flex gap-3"
        style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }}
      >
        <Button type="button" variant="outline" size="xl" className="flex-1" onClick={onDone}>
          건너뛰기
        </Button>
        <Button type="submit" size="xl" disabled={pending} className="flex-1">
          {pending ? "저장 중..." : "저장"}
        </Button>
      </div>
    </form>
  );
}
