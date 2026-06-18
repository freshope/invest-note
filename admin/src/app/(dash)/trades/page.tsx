"use client";

import { adminApi, type TradeRow } from "@/lib/api";
import { DataTablePage, type Column } from "@/components/DataTablePage";
import { fmtText, fmtNum, fmtDateTime } from "@/lib/format";

// trades 는 읽기 전용(PnL cascade 위험으로 쓰기는 후속 spec). cross-user 가시성(admin pool).
const columns: Column<TradeRow>[] = [
  { header: "종목", cell: (r) => fmtText(r.asset_name) },
  { header: "티커", cell: (r) => fmtText(r.ticker_symbol) },
  { header: "구분", cell: (r) => fmtText(r.trade_type) },
  { header: "시장", cell: (r) => fmtText(r.market_type) },
  {
    header: "가격",
    cell: (r) => <span className="tabular-nums">{fmtNum(r.price)}</span>,
    className: "text-right",
  },
  {
    header: "수량",
    cell: (r) => <span className="tabular-nums">{fmtNum(r.quantity)}</span>,
    className: "text-right",
  },
  { header: "거래일시", cell: (r) => fmtDateTime(r.traded_at) },
];

export default function TradesPage() {
  return (
    <DataTablePage
      title="거래"
      queryKey="trades"
      fetchList={adminApi.trades}
      columns={columns}
      searchPlaceholder="종목명·티커 검색"
    />
  );
}
