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
import {
  convertAssetSeries,
  convertDailySeries,
  convertInvestedAmount,
  convertItems,
} from "./asset-history-convert";
import { accountsApi, type AssetHistoryPoint, type AssetHistoryItem } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import { signColor, formatMoney, formatPnLCurrency, formatFxRate } from "@/lib/format";
import { useFxRate } from "@/hooks/useFxRate";
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

  // US 종목뷰일 때만 자산 추이를 원화로 통일한다(BE series 는 country 스코프 native=USD).
  // Phase B overlay 철학: BE 무변경, FE 에서 현재 환율로 환산(historical 아님 — 안내 문구로 명시).
  const isUsStock = isStockView && country === "US";
  const { usdkrw } = useFxRate(isUsStock);
  // 환율 미상(USD)이면 환산 불가 — 조용한 USD-as-KRW 금지(아래에서 안내 + 차트/헤더 비표시).
  const fxBlocked = isUsStock && usdkrw == null;
  // 차트·헤드라인 입력 통화 일관: US 는 native×현재환율로 KRW 통일, 그 외(KR 종목·계좌뷰)는 그대로.
  const rate = isUsStock ? usdkrw : null;

  // BE series(US 는 USD)를 현재 환율로 KRW 환산. KR/계좌뷰는 원본 그대로(환산 헬퍼는 순수 함수).
  const series = useMemo<AssetHistoryPoint[]>(
    () => (data ? convertAssetSeries(data.series, rate) : []),
    [data, rate],
  );

  const investedAmount = useMemo<number | null>(
    () => (data ? convertInvestedAmount(data.investedAmount, rate) : null),
    [data, rate],
  );

  // 일별 손익 시계열 — items(최신 먼저)의 change 를 날짜 오름차순으로 변환. US 는 KRW 환산.
  const dailySeries = useMemo<AssetHistoryPoint[]>(
    () => (data ? convertDailySeries(data.items, rate) : []),
    [data, rate],
  );

  // 최신 점은 환산된 series/dailySeries 에서 도출 — focus(차트가 통지하는 KRW 점)와 단일 소스 일치.
  const latestPoint = series.length ? series[series.length - 1] : null;
  const latestDaily = dailySeries.length ? dailySeries[dailySeries.length - 1] : null;
  const display = focus ?? (tab === "daily" ? latestDaily : latestPoint);
  // USD 보조 = KRW / 현재환율(native×rate 의 역). US 종목뷰 + 환율 정상일 때만 병기.
  const displayNativeUsd = isUsStock && usdkrw != null && display ? display.value / usdkrw : null;

  // 일별 내역 표의 '자산'(value)·'전일대비'(change)는 series/dailySeries 와 동일 데이터라 KRW 통일.
  // '종가'(close)는 1주당 가격이라 native(USD) 유지(포트폴리오 금액이 아님). 환율 미상이면 원본.
  const items = useMemo<AssetHistoryItem[]>(
    () => (data ? convertItems(data.items, rate) : []),
    [data, rate],
  );

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
                  {/* 일별 손익 탭만 부호 색상·'+' 접두 적용, 자산 탭은 고정색 */}
                  {fxBlocked ? (
                    // 환율 미상(USD) — 조용한 환산 금지. 환산 불가 안내만 노출.
                    <p className="text-[20px] font-bold text-muted-foreground">환율 확인 중</p>
                  ) : (
                    <p
                      className={cn(
                        "text-[24px] font-bold tabular-nums",
                        tab === "daily"
                          ? signColor(display?.value ?? 0, "muted")
                          : "text-foreground",
                      )}
                    >
                      {display ? (
                        <>
                          {tab === "daily" && display.value > 0 ? "+" : ""}
                          <CountUpNumber value={display.value} />
                        </>
                      ) : (
                        0
                      )}
                      원
                      {displayNativeUsd != null && (
                        <span className="ml-1.5 text-[14px] font-normal text-muted-foreground">
                          ({tab === "daily"
                            ? formatPnLCurrency(displayNativeUsd, "USD")
                            : formatMoney(displayNativeUsd, "USD")})
                        </span>
                      )}
                    </p>
                  )}
                </div>
                {/* 환율 미상(US)이면 차트도 native(USD)를 KRW 단위 차트에 그리는 셈이라 비표시(조용한 혼재 금지). */}
                {fxBlocked ? (
                  <div className="mt-3 flex h-[200px] items-center justify-center text-[13px] text-muted-foreground">
                    환율을 불러오면 원화 기준 차트를 표시해요.
                  </div>
                ) : (
                  <>
                    {/* 스코프(계좌/종목) 변경 시 remount → 팬 윈도우를 새 데이터의 최신으로 리셋 */}
                    <TabsContent value="asset" className="mt-3">
                      <AssetHistoryChart
                        key={`${effectiveAccountId ?? "all"}:${ticker ?? ""}`}
                        series={series}
                        investedAmount={investedAmount}
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
                  </>
                )}
              </Tabs>
              <div className="space-y-1">
                <p className="text-[11px] text-muted-foreground">
                  자산은 보유 종목 평가액 합계예요(예수금 제외).
                </p>
                {isUsStock && usdkrw != null && (
                  <p className="text-[11px] text-muted-foreground">
                    환율 {formatFxRate(usdkrw)} 기준으로 원화 환산했어요(일자별이 아닌 현재 환율 적용).
                  </p>
                )}
                {fxBlocked && (
                  <p className={cn("text-[11px]", PNL_COLORS.fall.text)}>
                    환율을 불러오지 못해 원화로 환산할 수 없어요. 잠시 후 다시 시도해 주세요.
                  </p>
                )}
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
            <AssetHistoryList items={items} isStockView={isStockView} />
          </div>
        </>
      )}
    </div>
  );
}
