"use client";

import { adminApi, type UserRow } from "@/lib/api";
import { DataTablePage, type Column } from "@/components/DataTablePage";
import { fmtDateTime } from "@/lib/format";

// users 는 읽기 전용. email 컬럼 없음(신원은 Supabase Auth 소유) — id(UUID) 표시.
const columns: Column<UserRow>[] = [
  {
    header: "ID",
    cell: (r) => <span className="font-mono text-[12px]">{r.id}</span>,
  },
  { header: "가입일", cell: (r) => fmtDateTime(r.created_at) },
];

export default function UsersPage() {
  return (
    <DataTablePage
      title="사용자"
      queryKey="users"
      fetchList={adminApi.users}
      columns={columns}
      searchPlaceholder="ID 검색"
    />
  );
}
