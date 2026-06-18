"use client";

import { adminApi, type CustomTagRow } from "@/lib/api";
import { DataTablePage, type Column } from "@/components/DataTablePage";
import { fmtText, fmtDateTime } from "@/lib/format";

// custom_tags 는 읽기 전용.
const columns: Column<CustomTagRow>[] = [
  { header: "라벨", cell: (r) => fmtText(r.label) },
  {
    header: "user_id",
    cell: (r) => (
      <span className="font-mono text-[12px]">{fmtText(r.user_id)}</span>
    ),
  },
  { header: "생성일", cell: (r) => fmtDateTime(r.created_at) },
];

export default function CustomTagsPage() {
  return (
    <DataTablePage
      title="커스텀 태그"
      queryKey="custom-tags"
      fetchList={adminApi.customTags}
      columns={columns}
      searchPlaceholder="라벨 검색"
    />
  );
}
