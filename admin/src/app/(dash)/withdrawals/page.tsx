"use client";

import { useQuery } from "@tanstack/react-query";
import { adminApi, type AccountDeletionStats } from "@/lib/api";
import { ApiErrorState } from "@/components/ApiErrorState";
import { DeletionTrendChart } from "@/components/DeletionTrendChart";

// 사유 코드 → 한글 라벨(BE me.py DeleteAccountRequest 고정 코드값 + 미선택 unspecified).
const REASON_LABELS: Record<string, string> = {
  not_useful: "기능이 부족해요",
  not_using: "자주 사용하지 않아요",
  privacy: "데이터·개인정보가 걱정돼요",
  other: "기타",
  unspecified: "미선택",
};

interface SummaryCard {
  label: string;
  value: (d: AccountDeletionStats) => string;
}

const CARDS: SummaryCard[] = [
  { label: "현재 가입자", value: (d) => d.total_users.toLocaleString() },
  { label: "누적 탈퇴", value: (d) => d.total_deletions.toLocaleString() },
  { label: "누적 탈퇴율", value: (d) => `${(d.churn_rate * 100).toFixed(1)}%` },
  { label: "최근 30일 탈퇴", value: (d) => d.deletions_30d.toLocaleString() },
  {
    label: "평균 사용 기간",
    value: (d) =>
      d.avg_lifetime_days == null ? "—" : `${d.avg_lifetime_days}일`,
  },
];

export default function WithdrawalsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin", "deletion-stats"],
    queryFn: () => adminApi.deletionStats(),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">탈퇴 통계</h1>

      {error ? (
        <ApiErrorState error={error} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
            {CARDS.map((card) => (
              <div
                key={card.label}
                className="rounded-lg border border-border bg-card p-5"
              >
                <p className="text-[13px] text-muted-foreground">{card.label}</p>
                <p className="mt-2 text-2xl font-bold tabular-nums">
                  {isLoading || !data ? "—" : card.value(data)}
                </p>
              </div>
            ))}
          </div>

          {data && <DeletionTrendChart data={data.trend} />}

          <div className="rounded-lg border border-border bg-card p-5">
            <p className="text-[13px] text-muted-foreground">탈퇴 사유 분포</p>
            {isLoading || !data ? (
              <p className="mt-2 text-[14px] text-muted-foreground">
                불러오는 중…
              </p>
            ) : data.reasons.length === 0 ? (
              <p className="mt-2 text-[14px] text-muted-foreground">
                데이터가 없습니다.
              </p>
            ) : (
              <ul className="mt-3 space-y-3">
                {data.reasons.map((r) => {
                  const pct =
                    data.total_deletions > 0
                      ? (r.count / data.total_deletions) * 100
                      : 0;
                  return (
                    <li key={r.reason} className="space-y-1">
                      <div className="flex items-center justify-between text-[14px]">
                        <span>{REASON_LABELS[r.reason] ?? r.reason}</span>
                        <span className="tabular-nums text-muted-foreground">
                          {r.count.toLocaleString()} ({pct.toFixed(0)}%)
                        </span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded bg-muted">
                        <div
                          className="h-full rounded bg-primary"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}
