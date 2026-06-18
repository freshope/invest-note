"use client";

import { adminApi, type NpsUnmatchedRow } from "@/lib/api";
import { DataTablePage, type Column } from "@/components/DataTablePage";
import { fmtText, fmtDate } from "@/lib/format";
import { NpsCreateDialog } from "./NpsCreateDialog";
import { NpsRowActions } from "./NpsRowActions";

// nps_unmatched 는 풀 CRUD(reconcile 큐). resolved_ticker 가 핵심 편집 필드.
const columns: Column<NpsUnmatchedRow>[] = [
  { header: "NPS 명칭", cell: (r) => fmtText(r.nps_name) },
  { header: "기준일", cell: (r) => fmtDate(r.nps_as_of) },
  { header: "보유 수준", cell: (r) => fmtText(r.holding_level) },
  { header: "해소 티커", cell: (r) => fmtText(r.resolved_ticker) },
];

export default function NpsUnmatchedPage() {
  return (
    <DataTablePage
      title="NPS 매칭 큐"
      queryKey="nps-unmatched"
      fetchList={adminApi.npsUnmatched.list}
      columns={columns}
      searchPlaceholder="NPS 명칭 검색"
      toolbar={<NpsCreateDialog />}
      rowActions={(row) => <NpsRowActions row={row} />}
    />
  );
}
