"use client";

import { useMemo } from "react";
import dynamic from "next/dynamic";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/base/Tabs";
import { calcPercent, fmtCompact } from "@/lib/format";
import { buildStockAllocation } from "@/lib/portfolio";
import type { Position, AccountSnapshot } from "@/lib/portfolio";
import type { DonutEntry } from "./AllocationPieChart";

const AllocationPieChart = dynamic(() => import("./AllocationPieChart"), {
  ssr: false,
  loading: () => <div style={{ height: 176 }} aria-hidden />,
});

const CHART_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
  "var(--chart-7)",
  "var(--chart-8)",
];

interface AllocationDonutProps {
  data: DonutEntry[];
  total: number;
  label: string;
  emptyMessage: string;
}

function AllocationDonut({ data, total, label, emptyMessage }: AllocationDonutProps) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-[13px] text-muted-foreground">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="relative h-44 [&_*:focus]:outline-none">
        <AllocationPieChart data={data} fallbackColors={CHART_COLORS} />
        {/* 중앙 텍스트 */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <p className="text-[11px] text-muted-foreground">{label}</p>
          <p className="text-[17px] font-bold tabular-nums text-foreground">{fmtCompact(total)}원</p>
        </div>
      </div>

      {/* 범례 */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
        {data.map((entry, i) => {
          const pct = calcPercent(entry.value, total);
          return (
            <div key={entry.name} className="flex items-center gap-1.5 min-w-0">
              <span
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{ backgroundColor: entry.color ?? CHART_COLORS[i % CHART_COLORS.length] }}
              />
              <span className="text-[12px] text-foreground truncate flex-1">{entry.name}</span>
              <span className="text-[12px] tabular-nums text-muted-foreground shrink-0">{pct}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

interface AllocationTabsProps {
  positions: Position[];
  snapshots: AccountSnapshot[];
  quotesError?: boolean;
}

export function AllocationTabs({ positions, snapshots, quotesError = false }: AllocationTabsProps) {
  // evaluation 은 이미 KRW(merge 단계 환산)이므로 그대로 비중 계산.
  const posData = useMemo<DonutEntry[]>(
    () => buildStockAllocation(positions, snapshots),
    [positions, snapshots],
  );

  const posTotal = useMemo(() => posData.reduce((s, d) => s + d.value, 0), [posData]);

  const snapData = useMemo<DonutEntry[]>(
    () =>
      snapshots
        .filter((s) => s.totalValue > 0)
        .map((s) => ({ name: s.account.name, value: s.totalValue })),
    [snapshots],
  );
  const snapTotal = useMemo(() => snapData.reduce((s, d) => s + d.value, 0), [snapData]);

  // 도넛이 비는 원인은 넷 — 보유 없음(전량 매도) / 시세 실패 / 환율 미상 / 시세 대기. 전부
  // "데이터 없음"으로 뭉치면 보유 종목이 있는데도 거래가 사라진 것처럼 보인다(오류 신고 사례).
  // 시세는 도착했는데 evaluation 이 null 이면 환율 미상(해외 보유) — "조회 중"이 영영 안 끝난다.
  const quotesArrived = positions.some((p) => p.currentPrice !== null);
  const emptyMessage =
    positions.length === 0
      ? "보유 중인 종목이 없어요"
      : quotesError
        ? "시세를 불러오지 못했어요"
        : quotesArrived
          ? "평가금액을 계산할 수 없어요"
          : "시세를 불러오는 중이에요";

  return (
    <div className="px-5">
      <div className="rounded-2xl bg-muted/60 p-4">
        <Tabs defaultValue="stock">
          <TabsList className="mb-4">
            <TabsTrigger value="stock">종목별</TabsTrigger>
            <TabsTrigger value="account">계좌별</TabsTrigger>
          </TabsList>
          <TabsContent value="stock">
            <AllocationDonut
              data={posData}
              total={posTotal}
              label="총자산"
              emptyMessage={emptyMessage}
            />
          </TabsContent>
          <TabsContent value="account">
            <AllocationDonut
              data={snapData}
              total={snapTotal}
              label="계좌 총액"
              emptyMessage={emptyMessage}
            />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
