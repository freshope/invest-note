"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeftIcon, ChevronDownIcon } from "lucide-react";
import { ErrorState } from "@/components/shared/ErrorState";
import { AccountFilter } from "@/components/shared/AccountFilter";
import { CountUpNumber } from "@/components/shared/CountUpNumber";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/base/Tabs";
import {
  useAccountFilter,
  useEffectiveAccountId,
} from "@/components/providers/AccountFilterProvider";
import { AssetHistoryChart } from "./AssetHistoryChart";
import { AssetDailyPnlChart } from "./AssetDailyPnlChart";
import { AssetHistoryList } from "./AssetHistoryList";
import { useAssetHistory } from "@/hooks/useAssetHistory";
import { accountsApi, type AssetHistoryPoint } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { signColor } from "@/lib/format";
import { PNL_COLORS } from "@/lib/constants/pnl-colors";
import { cn } from "@/lib/utils";

function Skeleton() {
  return (
    <div className="px-5 pt-2 pb-6 space-y-4 animate-pulse">
      <div className="rounded-2xl bg-muted/60 h-[280px]" />
      <div className="space-y-2 px-1">
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className="h-8 rounded bg-muted/60" />
        ))}
      </div>
    </div>
  );
}

interface AssetHistoryViewProps {
  ticker: string | null;
  country: string | null;
  name: string | null;
  onBack: () => void;
  /** 종목 view(패널)에서만 전달 — 헤더 종목명으로 종목 전환 바텀시트를 연다. 라우트(계좌 view)는 미전달. */
  onSwitchStock?: () => void;
}

/**
 * 자산 변화 본체 — 라우트(/assets)와 종목상세 패널이 공유.
 * 전체 높이 flex 컬럼: 헤더·요약차트 카드는 고정, 일별 내역 목록만 내부 스크롤(테이블 헤더 sticky).
 * 부모(라우트 fixed 래퍼 / FullScreenPanelContent)가 뷰포트 높이를 제공한다.
 */
export function AssetHistoryView({ ticker, country, name, onBack, onSwitchStock }: AssetHistoryViewProps) {
  const isStockView = ticker != null;

  const { data: accounts = [] } = useQuery({
    queryKey: queryKeys.accounts,
    queryFn: accountsApi.list,
  });
  const { setSelectedAccountId } = useAccountFilter();
  const effectiveAccountId = useEffectiveAccountId(accounts);

  // 계좌뷰·종목뷰 모두 계좌 필터를 적용한다(선택 시 해당 계좌의 보유분만, 전체면 합산).
  const { data, loading, reloading, error, refetch } = useAssetHistory({
    accountId: effectiveAccountId,
    ticker,
    country,
  });

  // 차트 탭 — 자산(누적 평가액 Area) / 일별 손익(전일대비 Bar).
  const [tab, setTab] = useState<"asset" | "daily">("asset");

  // 차트에서 보이는 가장 우측(최근) 점 — 헤더가 이 점의 날짜·금액을 표시.
  // 탭에 따라 value 의 의미가 다름(자산: 평가액 / 일별 손익: 전일대비).
  const [focus, setFocus] = useState<AssetHistoryPoint | null>(null);
  // 스코프(계좌/종목) 전환 시 초기화 → 차트가 새 우측점을 통지할 때까지 최신값 표시.
  // effect 대신 렌더 중 상태 조정 패턴 사용(react-hooks/set-state-in-effect 회피).
  const scopeKey = `${effectiveAccountId ?? ""}|${ticker ?? ""}`;
  const [prevScopeKey, setPrevScopeKey] = useState(scopeKey);
  if (scopeKey !== prevScopeKey) {
    setPrevScopeKey(scopeKey);
    setFocus(null);
  }

  const title = isStockView ? `${name ?? "종목"} 자산 추이` : "내 자산 추이";
  const showFilter = accounts.length >= 2;

  // 일별 손익 시계열 — items(최신 먼저)의 change 를 날짜 오름차순으로 변환.
  // BE 가 계산한 전일대비를 그대로 사용해 '일별 내역' 표와 값이 일치한다.
  const dailySeries = useMemo<AssetHistoryPoint[]>(
    () =>
      data
        ? [...data.items].reverse().map((it) => ({ date: it.date, value: it.change }))
        : [],
    [data],
  );

  const latestPoint =
    data && data.series.length ? data.series[data.series.length - 1] : null;
  const latestDaily = dailySeries.length ? dailySeries[dailySeries.length - 1] : null;
  const display = focus ?? (tab === "daily" ? latestDaily : latestPoint);

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* 헤더 — 종목상세/거래상세 패널과 동일 레이아웃(h-14, safe-area, 중앙 타이틀) */}
      <div
        className="shrink-0 bg-background"
        style={{ paddingTop: "var(--safe-area-inset-top, env(safe-area-inset-top))" }}
      >
        <div className="relative flex h-14 items-center px-2">
          <button
            type="button"
            onClick={onBack}
            className="flex h-10 w-10 items-center justify-center rounded-full text-foreground transition-colors hover:bg-muted active:bg-muted"
            aria-label="뒤로"
          >
            <ChevronLeftIcon className="h-6 w-6" strokeWidth={2.2} />
          </button>
          {/* 컨테이너는 pointer-events-none 유지 → 클릭이 뒤로가기 버튼으로 통과. 중앙 버튼만 pointer-events-auto */}
          <div className="absolute inset-x-0 flex justify-center px-14 pointer-events-none">
            {isStockView && onSwitchStock ? (
              <button
                type="button"
                onClick={onSwitchStock}
                className="pointer-events-auto inline-flex max-w-full items-center gap-1 text-[17px] font-bold text-foreground"
                aria-label="종목 변경"
              >
                <span className="min-w-0 truncate">{title}</span>
                <ChevronDownIcon className="size-4 shrink-0 text-muted-foreground" strokeWidth={2.4} />
              </button>
            ) : (
              <span className="min-w-0 truncate text-[17px] font-bold text-foreground">{title}</span>
            )}
          </div>
        </div>
        {showFilter && (
          <AccountFilter
            accounts={accounts}
            value={effectiveAccountId}
            onChange={setSelectedAccountId}
          />
        )}
      </div>

      {/* 본문 — 요약+차트 카드는 고정, 일별 내역만 내부 스크롤 */}
      {loading || reloading ? (
        <Skeleton />
      ) : error ? (
        <div className="flex-1 min-h-0">
          <ErrorState onRetry={() => refetch()} />
        </div>
      ) : !data ? null : (
        <>
          {/* 요약 + 차트 카드 (홈 도넛 카드와 동일한 rounded-2xl bg-muted/60 패턴) */}
          <div className="shrink-0 px-5 pt-2">
            <div className="rounded-2xl bg-muted/60 p-4 space-y-3">
              <Tabs
                value={tab}
                onValueChange={(v) => {
                  setTab(v as "asset" | "daily");
                  // 탭별로 value 의미가 다르므로 리셋 → 새 차트가 우측점을 다시 통지.
                  setFocus(null);
                }}
              >
                <TabsList>
                  <TabsTrigger value="asset">자산</TabsTrigger>
                  <TabsTrigger value="daily">일별 손익</TabsTrigger>
                </TabsList>
                <div className="mt-3">
                  <p className="text-[12px] text-muted-foreground">
                    {display ? display.date.replace(/-/g, ".") : "현재 자산"}
                  </p>
                  {tab === "daily" ? (
                    <p
                      className={cn(
                        "text-[24px] font-bold tabular-nums",
                        signColor(display?.value ?? 0, "muted"),
                      )}
                    >
                      {display ? (
                        <>
                          {display.value > 0 ? "+" : ""}
                          <CountUpNumber value={display.value} />
                        </>
                      ) : (
                        0
                      )}
                      원
                    </p>
                  ) : (
                    <p className="text-[24px] font-bold tabular-nums text-foreground">
                      {display ? <CountUpNumber value={display.value} /> : 0}원
                    </p>
                  )}
                </div>
                {/* 스코프(계좌/종목) 변경 시 remount → 팬 윈도우를 새 데이터의 최신으로 리셋 */}
                <TabsContent value="asset" className="mt-3">
                  <AssetHistoryChart
                    key={`${effectiveAccountId ?? "all"}:${ticker ?? ""}`}
                    series={data.series}
                    investedAmount={data.investedAmount}
                    onFocusChange={setFocus}
                  />
                </TabsContent>
                <TabsContent value="daily" className="mt-3">
                  <AssetDailyPnlChart
                    key={`${effectiveAccountId ?? "all"}:${ticker ?? ""}`}
                    series={dailySeries}
                    onFocusChange={setFocus}
                  />
                </TabsContent>
              </Tabs>
              <div className="space-y-1">
                <p className="text-[11px] text-muted-foreground">
                  자산은 보유 종목 평가액 합계예요(예수금 제외).
                </p>
                {data.incomplete && (
                  <p className={cn("text-[11px]", PNL_COLORS.fall.text)}>
                    일부 종목 시세를 불러오지 못해 직전 종가로 보정한 값이 포함돼 있어요.
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* 일별 내역 — 섹션 라벨(다른 페이지 섹션 패턴) + 내부 스크롤 표 */}
          <div className="shrink-0 px-5 pt-5 pb-1">
            <p className="text-[13px] font-semibold text-muted-foreground">일별 내역</p>
          </div>
          <div
            className="flex-1 min-h-0 overflow-y-auto px-5"
            style={{ paddingBottom: "calc(2.5rem + var(--safe-area-inset-bottom, env(safe-area-inset-bottom)))" }}
          >
            <AssetHistoryList items={data.items} isStockView={isStockView} />
          </div>
        </>
      )}
    </div>
  );
}
