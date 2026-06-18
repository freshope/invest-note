"use client";

import { adminApi, type StockRow } from "@/lib/api";
import { DataTablePage, type Column } from "@/components/DataTablePage";
import { fmtText, fmtNum } from "@/lib/format";
import { StockEditDialog } from "./StockEditDialog";

// stocks 는 읽기 + 수정(삭제 없음). 글로벌 마스터. 편집은 seed 비-소유 필드만(BE 화이트리스트).
const columns: Column<StockRow>[] = [
  { header: "국가", cell: (r) => fmtText(r.country_code) },
  { header: "티커", cell: (r) => fmtText(r.ticker) },
  { header: "종목명", cell: (r) => fmtText(r.asset_name) },
  { header: "시장", cell: (r) => fmtText(r.market) },
  { header: "섹터", cell: (r) => fmtText(r.sector) },
  {
    header: "시총순위",
    cell: (r) => <span className="tabular-nums">{fmtNum(r.marcap_rank)}</span>,
    className: "text-right",
  },
  {
    header: "활성",
    cell: (r) => (r.is_active === false ? "비활성" : "활성"),
  },
];

export default function StocksPage() {
  return (
    <DataTablePage
      title="종목"
      queryKey="stocks"
      fetchList={adminApi.stocks.list}
      columns={columns}
      searchPlaceholder="종목명·티커 검색"
      rowActions={(row) => <StockEditDialog row={row} />}
    />
  );
}
