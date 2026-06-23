"use client";

import { useQuery } from "@tanstack/react-query";
import { adminApi, type AdminStats } from "@/lib/api";
import { ApiErrorState } from "@/components/ApiErrorState";
import { UserGrowthChart } from "@/components/UserGrowthChart";

interface StatCard {
  key: keyof AdminStats;
  label: string;
}

const CARDS: StatCard[] = [
  { key: "users", label: "사용자" },
  { key: "accounts", label: "계좌" },
  { key: "trades", label: "거래" },
  { key: "stocks", label: "종목" },
  { key: "nps_unmatched", label: "NPS 매칭 큐" },
  { key: "broker_statements", label: "거래내역서 제출" },
];

export default function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin", "stats"],
    queryFn: () => adminApi.stats(),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">대시보드</h1>

      {error ? (
        <ApiErrorState error={error} />
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
          {CARDS.map((card) => (
            <div
              key={card.key}
              className="rounded-lg border border-border bg-card p-5"
            >
              <p className="text-[13px] text-muted-foreground">{card.label}</p>
              <p className="mt-2 text-2xl font-bold tabular-nums">
                {isLoading
                  ? "—"
                  : (data?.[card.key]?.toLocaleString() ?? "—")}
              </p>
            </div>
          ))}
        </div>
      )}

      <UserGrowthChart />
    </div>
  );
}
