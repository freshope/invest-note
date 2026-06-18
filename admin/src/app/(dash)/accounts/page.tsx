"use client";

import { adminApi, type AccountRow } from "@/lib/api";
import { DataTablePage, type Column } from "@/components/DataTablePage";
import { fmtText, fmtNum, fmtDateTime } from "@/lib/format";

// accounts 는 읽기 전용. cross-user 가시성(admin pool).
const columns: Column<AccountRow>[] = [
  { header: "이름", cell: (r) => fmtText(r.name) },
  { header: "증권사", cell: (r) => fmtText(r.broker) },
  {
    header: "현금잔액",
    cell: (r) => <span className="tabular-nums">{fmtNum(r.cash_balance)}</span>,
    className: "text-right",
  },
  {
    header: "user_id",
    cell: (r) => (
      <span className="font-mono text-[12px]">{fmtText(r.user_id)}</span>
    ),
  },
  { header: "생성일", cell: (r) => fmtDateTime(r.created_at) },
];

export default function AccountsPage() {
  return (
    <DataTablePage
      title="계좌"
      queryKey="accounts"
      fetchList={adminApi.accounts}
      columns={columns}
      searchPlaceholder="이름 검색"
    />
  );
}
