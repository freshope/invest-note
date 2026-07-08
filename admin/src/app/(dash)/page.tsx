"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { adminApi, type AdminStats } from "@/lib/api";
import { ApiErrorState } from "@/components/ApiErrorState";
import { UserGrowthChart } from "@/components/UserGrowthChart";

type StatCard =
  | {
      kind: "count";
      key: keyof AdminStats;
      label: string;
      // 있으면 "오늘 / 누적" 표시(등록수 카드). 없으면 누적만.
      todayKey?: keyof AdminStats;
      // 있으면 카드가 상세 페이지 진입점이 됨.
      href?: string;
    }
  // DAU/WAU/MAU 단일 카드(값 슬래시 구분).
  | { kind: "active" };

const CARDS: StatCard[] = [
  { kind: "count", key: "users", label: "사용자", todayKey: "users_today", href: "/users" },
  { kind: "count", key: "deletions", label: "탈퇴", todayKey: "deletions_today", href: "/withdrawals" },
  { kind: "active" },
  { kind: "count", key: "accounts", label: "계좌", todayKey: "accounts_today", href: "/accounts" },
  { kind: "count", key: "trades", label: "거래", todayKey: "trades_today", href: "/trades" },
  { kind: "count", key: "feedback", label: "사용자 의견", todayKey: "feedback_today", href: "/boards/feedback" },
  { kind: "count", key: "bug_reports", label: "오류 신고", todayKey: "bug_reports_today", href: "/boards/bug-report" },
  {
    kind: "count",
    key: "broker_statements",
    label: "거래내역서 제출",
    todayKey: "broker_statements_today",
    href: "/boards/broker-statement",
  },
  { kind: "count", key: "stocks", label: "종목", href: "/stocks" },
  { kind: "count", key: "nps_unmatched", label: "NPS 매칭 큐", href: "/nps-unmatched" },
];

function fmt(n: number | undefined, loading: boolean): string {
  if (loading) return "—";
  return n?.toLocaleString() ?? "—";
}

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
        <>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
            {CARDS.map((card) => {
              if (card.kind === "active") {
                return (
                  <div
                    key="active"
                    className="rounded-lg border border-border bg-card p-5"
                  >
                    <p className="text-[13px] text-muted-foreground">DAU/WAU/MAU</p>
                    <p className="mt-2 text-2xl font-bold tabular-nums">
                      {fmt(data?.dau, isLoading)}/{fmt(data?.wau, isLoading)}/
                      {fmt(data?.mau, isLoading)}
                    </p>
                    <p className="mt-1 text-[12px] text-muted-foreground">
                      last_sign_in 기준
                    </p>
                  </div>
                );
              }
              const body = (
                <>
                  <p className="text-[13px] text-muted-foreground">{card.label}</p>
                  {card.todayKey ? (
                    <>
                      <p className="mt-2 text-2xl font-bold tabular-nums">
                        {fmt(data?.[card.todayKey], isLoading)}
                        <span className="font-normal text-muted-foreground">
                          {" / "}
                          {fmt(data?.[card.key], isLoading)}
                        </span>
                      </p>
                      <p className="mt-1 text-[12px] text-muted-foreground">오늘 / 누적</p>
                    </>
                  ) : (
                    <p className="mt-2 text-2xl font-bold tabular-nums">
                      {fmt(data?.[card.key], isLoading)}
                    </p>
                  )}
                </>
              );
              const cls =
                "rounded-lg border border-border bg-card p-5" +
                (card.href ? " transition-colors hover:bg-accent" : "");
              return card.href ? (
                <Link key={card.key} href={card.href} className={cls}>
                  {body}
                </Link>
              ) : (
                <div key={card.key} className={cls}>
                  {body}
                </div>
              );
            })}
          </div>
        </>
      )}

      <UserGrowthChart />
    </div>
  );
}
