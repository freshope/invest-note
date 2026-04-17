"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/base/Button";
import { Label } from "@/components/base/Label";
import { Textarea } from "@/components/base/Textarea";
import { tradesApi } from "@/lib/api-client";
import type { StrategyType, EmotionType, ReasoningTag } from "@/types/database";
import { STRATEGIES, EMOTIONS, REASONING_TAGS } from "./constants";

interface TradeMetaBuyFormProps {
  tradeId: string;
  onDone: () => void;
}

export function TradeMetaBuyForm({ tradeId, onDone }: TradeMetaBuyFormProps) {
  const router = useRouter();
  const [strategy, setStrategy] = useState<StrategyType | "">("");
  const [emotion, setEmotion] = useState<EmotionType | "">("");
  const [tags, setTags] = useState<ReasoningTag[]>([]);
  const [buyReason, setBuyReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  function toggleTag(tag: ReasoningTag) {
    setTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      await tradesApi.update(tradeId, {
        strategy_type: strategy || null,
        emotion: emotion || null,
        reasoning_tags: tags,
        buy_reason: buyReason.trim() || null,
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

        {/* 분석 태그 */}
        <div className="space-y-2">
          <Label>분석 태그 <span className="text-[12px] font-normal text-muted-foreground">(복수 선택)</span></Label>
          <div className="grid grid-cols-2 gap-2">
            {REASONING_TAGS.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => toggleTag(t.value)}
                className={`rounded-xl border py-2.5 text-[13px] font-semibold transition-colors ${
                  tags.includes(t.value)
                    ? "bg-primary text-primary-foreground border-primary"
                    : "border-border bg-muted/50 text-muted-foreground"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* 매매 이유 */}
        <div className="space-y-1.5">
          <Label htmlFor="buy_reason">매수 근거 <span className="text-[12px] font-normal text-muted-foreground">(선택)</span></Label>
          <Textarea
            id="buy_reason"
            value={buyReason}
            onChange={(e) => setBuyReason(e.target.value)}
            placeholder="매수한 근거를 간단히 적어주세요"
            rows={3}
          />
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
