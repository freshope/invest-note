"use client";

import Link from "next/link";
import { adminApi, type ImportBatchRow } from "@/lib/api";
import { DataTablePage, type Column } from "@/components/DataTablePage";
import { Button } from "@/components/base/Button";
import { fmtText, fmtNum, fmtDateTime } from "@/lib/format";

// broker_key(내부값) → 표시 라벨. 미매핑 키는 원본 그대로 노출(신규 파서 드리프트 안전).
const BROKER_LABELS: Record<string, string> = {
  toss_pdf: "토스",
  samsung_xlsx: "삼성",
  shinhan_pdf: "신한",
  mirae_pdf: "미래에셋",
};

function brokerLabel(key: string): string {
  return BROKER_LABELS[key] ?? key;
}

// 원장 배치는 읽기 전용(append-only). cross-user 가시성(admin pool).
const columns: Column<ImportBatchRow>[] = [
  { header: "증권사", cell: (r) => brokerLabel(r.broker_key) },
  {
    header: "파일명",
    cell: (r) => (
      <span className="block max-w-[220px] truncate">{fmtText(r.filename)}</span>
    ),
  },
  { header: "사용자", cell: (r) => fmtText(r.email) },
  { header: "업로드", cell: (r) => fmtDateTime(r.created_at) },
  {
    header: "등록",
    cell: (r) =>
      r.committed_at ? (
        <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[12px] text-primary">
          등록
        </span>
      ) : (
        <span className="rounded bg-muted px-1.5 py-0.5 text-[12px] text-muted-foreground">
          미리보기
        </span>
      ),
  },
  {
    header: "행수",
    // 거래 행 / 전체 행. 원장은 무손실이라 비거래(오류·헤더) 행이 섞일 수 있음.
    cell: (r) => (
      <span className="tabular-nums">
        {fmtNum(r.trade_row_count)}
        <span className="text-muted-foreground"> / {fmtNum(r.entry_count)}</span>
      </span>
    ),
    className: "text-right",
  },
];

export default function ImportLedgerPage() {
  return (
    <DataTablePage
      title="일괄등록 원장"
      queryKey="import-batches"
      fetchList={adminApi.importBatches.list}
      columns={columns}
      searchPlaceholder="파일명·이메일 검색"
      rowActions={(row) => (
        <Button asChild variant="outline" size="sm">
          <Link href={`/import-ledger/${row.id}`}>상세</Link>
        </Button>
      )}
    />
  );
}
