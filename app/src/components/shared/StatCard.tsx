import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  valueClass?: string;
}

export function StatCard({ label, value, sub, valueClass }: StatCardProps) {
  return (
    <div className="rounded-2xl bg-muted/60 p-3.5 space-y-0.5">
      <p className="text-[11px] font-semibold text-muted-foreground">{label}</p>
      {/* 값이 카드 폭을 넘겨도 옆 카드 위로 넘쳐 겹치지 않도록 카드 안에서 자른다.
          잘린 사실이 보이도록 clip 이 아니라 말줄임(truncate) — 잘린 숫자가 그럴듯한 다른
          금액으로 읽히면 겹침보다 나쁘다. */}
      <p className={cn("truncate text-[15px] font-bold tabular-nums leading-snug", valueClass)}>{value}</p>
      {sub && <p className="text-[10px] text-muted-foreground">{sub}</p>}
    </div>
  );
}
