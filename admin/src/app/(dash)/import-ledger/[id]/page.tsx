"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { adminApi, type ImportLedgerEntry } from "@/lib/api";
import { ApiErrorState } from "@/components/ApiErrorState";
import { Button } from "@/components/base/Button";
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from "@/components/base/Table";
import { fmtText, fmtNum, fmtDateTime } from "@/lib/format";
import { AuthorCell, authorFallback } from "@/components/AuthorCell";

const BROKER_LABELS: Record<string, string> = {
  toss_pdf: "토스",
  samsung_xlsx: "삼성",
  shinhan_pdf: "신한",
  mirae_pdf: "미래에셋",
};

function MetaRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-[12px] text-muted-foreground">{label}</dt>
      <dd className="break-all text-[14px]">{value}</dd>
    </div>
  );
}

export default function ImportLedgerDetailPage() {
  const params = useParams<{ id: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin", "import-batch", params.id],
    queryFn: () => adminApi.importBatches.get(params.id),
    enabled: !!params.id,
  });

  if (error) return <ApiErrorState error={error} />;
  if (isLoading || !data) {
    return <p className="text-sm text-muted-foreground">불러오는 중...</p>;
  }

  const b = data.batch;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button asChild variant="outline" size="sm">
          <Link href="/import-ledger">
            <ArrowLeft className="mr-1 h-4 w-4" />
            목록
          </Link>
        </Button>
        <h1 className="text-xl font-bold">
          {BROKER_LABELS[b.broker_key] ?? b.broker_key} · {fmtText(b.filename)}
        </h1>
        {b.committed_at ? (
          <span className="rounded bg-primary/10 px-2 py-0.5 text-[12px] text-primary">
            등록됨
          </span>
        ) : (
          <span className="rounded bg-muted px-2 py-0.5 text-[12px] text-muted-foreground">
            미리보기(미등록)
          </span>
        )}
      </div>

      {/* 배치 메타 */}
      <dl className="grid grid-cols-2 gap-4 rounded-lg border border-border bg-card p-5 md:grid-cols-3">
        <MetaRow
          label="사용자"
          value={
            <AuthorCell
              avatarUrl={b.author_avatar_url}
              displayName={b.author_display_name}
              fallback={b.email ?? authorFallback()}
            />
          }
        />
        <MetaRow label="파서 버전" value={fmtText(b.parser_version)} />
        <MetaRow label="업로드" value={fmtDateTime(b.created_at)} />
        <MetaRow label="파싱" value={fmtDateTime(b.parsed_at)} />
        <MetaRow label="등록" value={fmtDateTime(b.committed_at)} />
        <MetaRow
          label="등록 계좌"
          value={fmtText(b.account_name) + (b.account_hint ? ` (힌트: ${b.account_hint})` : "")}
        />
        <MetaRow
          label="행수 (거래 / 전체)"
          value={`${fmtNum(b.trade_row_count)} / ${fmtNum(b.entry_count)}`}
        />
        <MetaRow
          label="파일"
          value={`${fmtText(b.content_type)} · ${fmtNum(b.size_bytes)} bytes`}
        />
        <MetaRow
          label="sha256"
          value={<span className="font-mono text-[11px]">{fmtText(b.content_sha256)}</span>}
        />
        <MetaRow
          label="storage_key"
          value={<span className="font-mono text-[11px]">{fmtText(b.storage_key)}</span>}
        />
      </dl>

      {/* 원장 행 */}
      <div className="rounded-lg border border-border bg-card">
        <div className="border-b border-border px-5 py-3 text-[13px] text-muted-foreground">
          원장 행 {data.entries.length}건 (append-only · 원문 무손실)
        </div>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">#</TableHead>
                <TableHead>유형</TableHead>
                <TableHead>종목</TableHead>
                <TableHead>티커/ISIN</TableHead>
                <TableHead>국가</TableHead>
                <TableHead className="text-right">수량</TableHead>
                <TableHead className="text-right">단가</TableHead>
                <TableHead className="text-right">수수료</TableHead>
                <TableHead className="text-right">세금</TableHead>
                <TableHead className="text-right">환율</TableHead>
                <TableHead>거래일(원문)</TableHead>
                <TableHead>raw</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.entries.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={12} className="text-center text-muted-foreground">
                    원장 행이 없습니다.
                  </TableCell>
                </TableRow>
              ) : (
                data.entries.map((e: ImportLedgerEntry) => (
                  <TableRow key={e.id}>
                    <TableCell className="tabular-nums">{e.source_row_no}</TableCell>
                    <TableCell>{fmtText(e.trade_type)}</TableCell>
                    <TableCell>{fmtText(e.asset_name)}</TableCell>
                    <TableCell className="font-mono text-[12px]">
                      {fmtText(e.ticker_hint ?? e.isin)}
                    </TableCell>
                    <TableCell>{fmtText(e.country_code)}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmtNum(e.quantity)}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmtNum(e.price)}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmtNum(e.commission)}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmtNum(e.tax)}</TableCell>
                    <TableCell className="text-right tabular-nums">{fmtNum(e.exchange_rate)}</TableCell>
                    <TableCell className="text-[12px]">{fmtText(e.traded_at_raw)}</TableCell>
                    <TableCell>
                      <details>
                        <summary className="cursor-pointer text-[12px] text-muted-foreground">
                          펼침
                        </summary>
                        <pre className="mt-1 max-w-[360px] overflow-x-auto rounded bg-muted p-2 text-[11px]">
                          {JSON.stringify(e.raw, null, 2)}
                        </pre>
                      </details>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  );
}
