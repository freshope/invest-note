"use client";

import { adminApi, type UserRow } from "@/lib/api";
import { DataTablePage, type Column } from "@/components/DataTablePage";
import { fmtDateTime, fmtText } from "@/lib/format";
import { AuthorCell } from "@/components/AuthorCell";

// users 는 읽기 전용. 신원/프로필은 user_profiles LEFT JOIN — 프로필 행 없으면 각 필드 null.
const columns: Column<UserRow>[] = [
  {
    header: "사용자",
    cell: (r) => (
      <AuthorCell
        avatarUrl={r.avatar_url}
        displayName={r.display_name}
        fallback="-"
      />
    ),
  },
  {
    header: "이메일",
    cell: (r) => (
      <span className="inline-flex items-center gap-1.5">
        {fmtText(r.email)}
        {r.email_verified === true && (
          <span className="rounded bg-green-100 px-1 py-0.5 text-[10px] font-medium text-green-700">
            인증
          </span>
        )}
      </span>
    ),
  },
  {
    header: "로그인 경로",
    cell: (r) =>
      r.providers && r.providers.length > 0 ? (
        <span className="flex flex-wrap gap-1">
          {r.providers.map((p) => (
            <span
              key={p}
              className="rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground"
            >
              {p}
            </span>
          ))}
        </span>
      ) : (
        "-"
      ),
  },
  {
    header: "보유 계좌수",
    cell: (r) => (
      <span className="tabular-nums">{(r.account_count ?? 0).toLocaleString()}</span>
    ),
  },
  {
    header: "총 거래수",
    cell: (r) => (
      <span className="tabular-nums">{(r.trade_count ?? 0).toLocaleString()}</span>
    ),
  },
  { header: "마지막 로그인", cell: (r) => fmtDateTime(r.last_sign_in) },
  { header: "가입일", cell: (r) => fmtDateTime(r.created_at) },
  {
    header: "ID",
    cell: (r) => <span className="font-mono text-[12px]">{r.id}</span>,
  },
];

export default function UsersPage() {
  return (
    <DataTablePage
      title="사용자"
      queryKey="users"
      fetchList={adminApi.users}
      columns={columns}
      searchPlaceholder="이메일·닉네임·ID 검색"
    />
  );
}
