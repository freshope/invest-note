"use client";

import { cn } from "@/lib/utils";
import { signColor, formatMoney } from "@/lib/format";
import type { AssetHistoryItem } from "@/lib/api-client";

function formatChange(change: number): string {
  if (change === 0) return "0";
  const sign = change > 0 ? "+" : "";
  return `${sign}${Math.round(change).toLocaleString("ko-KR")}`;
}

function formatValue(value: number): string {
  return Math.round(value).toLocaleString("ko-KR");
}

interface AssetHistoryListProps {
  items: AssetHistoryItem[];
  /** 종목뷰면 종가·수량 열 추가 */
  isStockView: boolean;
  /** 종목뷰 종가 컬럼 통화(native). KR=KRW, US=USD. 자산/전일대비는 항상 KRW. */
  closeCurrency?: string;
  /** 변화량 컬럼 라벨 — 표시 단위에 따라 전일대비/전주대비/전월대비. */
  deltaLabel?: string;
}

export function AssetHistoryList({
  items,
  isStockView,
  closeCurrency = "KRW",
  deltaLabel = "전일대비",
}: AssetHistoryListProps) {
  if (items.length === 0) {
    return (
      <div className="py-8 text-center text-[13px] text-muted-foreground">
        표시할 내역이 없어요
      </div>
    );
  }

  // 헤더 셀은 sticky top-0 으로 스크롤 컨테이너 상단에 고정(내용만 스크롤). bg-background 로 비침 방지.
  // 하단선은 border 대신 box-shadow(inset) 사용 — sticky + border-collapse 에서 border 는 스크롤 시
  // 그리드에서 분리돼 사라지므로, th 자체에 그려지는 shadow 로 항상 따라오게 한다.
  const thBase =
    "sticky top-0 z-10 bg-background py-2 font-medium shadow-[inset_0_-1px_0_0_var(--border)]";

  return (
    <table className="w-full text-[13px] tabular-nums">
      <thead>
        <tr className="text-[12px] text-muted-foreground">
          <th className={cn(thBase, "text-left")}>날짜</th>
          <th className={cn(thBase, "text-right")}>자산</th>
          <th className={cn(thBase, "text-right")}>{deltaLabel}</th>
          {isStockView && <th className={cn(thBase, "text-right")}>종가</th>}
          {isStockView && <th className={cn(thBase, "text-right")}>수량</th>}
        </tr>
      </thead>
      <tbody>
        {items.map((it) => (
          <tr key={it.date} className="border-t border-border/60 first:border-t-0">
            <td className="py-2 text-left text-muted-foreground">{it.date}</td>
            <td className="py-2 text-right font-medium text-foreground">
              {formatValue(it.value)}
            </td>
            <td className={cn("py-2 text-right", signColor(it.change, "muted"))}>
              {formatChange(it.change)}
            </td>
            {isStockView && (
              <td className="py-2 text-right text-foreground">
                {it.close != null
                  ? closeCurrency === "KRW"
                    ? formatValue(it.close)
                    : formatMoney(it.close, closeCurrency)
                  : "-"}
              </td>
            )}
            {isStockView && (
              <td className="py-2 text-right text-muted-foreground">
                {it.qty != null ? it.qty.toLocaleString("ko-KR") : "-"}
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
