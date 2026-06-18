"use client";

import { useState, type ReactNode } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { Search } from "lucide-react";
import type { AdminListResponse, AdminListParams } from "@/lib/api";
import { ApiErrorState } from "@/components/ApiErrorState";
import { Input } from "@/components/base/Input";
import { Button } from "@/components/base/Button";
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from "@/components/base/Table";

const PAGE_SIZE = 50;

export interface Column<T> {
  /** 헤더 라벨 */
  header: string;
  /** 셀 렌더러. row 전체를 받아 ReactNode 반환. */
  cell: (row: T) => ReactNode;
  className?: string;
}

interface DataTablePageProps<T> {
  title: string;
  /** react-query 키 prefix(테이블 식별). */
  queryKey: string;
  /** 목록 조회 함수(엔벨로프 반환). */
  fetchList: (params: AdminListParams) => Promise<AdminListResponse<T>>;
  columns: Column<T>[];
  searchPlaceholder?: string;
  /** 각 행 우측 액션(수정/삭제 버튼 등). 읽기 전용 테이블은 미전달. */
  rowActions?: (row: T) => ReactNode;
  /** 헤더 우측 영역(예: 생성 버튼). */
  toolbar?: ReactNode;
}

export function DataTablePage<T>({
  title,
  queryKey,
  fetchList,
  columns,
  searchPlaceholder,
  rowActions,
  toolbar,
}: DataTablePageProps<T>) {
  const [page, setPage] = useState(1);
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["admin", queryKey, page, q],
    queryFn: () => fetchList({ page, page_size: PAGE_SIZE, q: q || undefined }),
    placeholderData: keepPreviousData,
  });

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const colCount = columns.length + (rowActions ? 1 : 0);

  function submitSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    setQ(qInput.trim());
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">{title}</h1>
        {toolbar}
      </div>

      <form onSubmit={submitSearch} className="flex items-center gap-2">
        <div className="relative max-w-xs flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
            placeholder={searchPlaceholder ?? "검색"}
            className="pl-9"
          />
        </div>
        <Button type="submit" variant="secondary" size="sm">
          검색
        </Button>
      </form>

      {error ? (
        <ApiErrorState error={error} />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  {columns.map((c, i) => (
                    <TableHead key={i} className={c.className}>
                      {c.header}
                    </TableHead>
                  ))}
                  {rowActions && (
                    <TableHead className="text-right">작업</TableHead>
                  )}
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell
                      colSpan={colCount}
                      className="py-8 text-center text-muted-foreground"
                    >
                      불러오는 중...
                    </TableCell>
                  </TableRow>
                ) : (data?.items.length ?? 0) === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={colCount}
                      className="py-8 text-center text-muted-foreground"
                    >
                      데이터가 없습니다.
                    </TableCell>
                  </TableRow>
                ) : (
                  data?.items.map((row, i) => (
                    <TableRow key={i}>
                      {columns.map((c, j) => (
                        <TableCell key={j} className={c.className}>
                          {c.cell(row)}
                        </TableCell>
                      ))}
                      {rowActions && (
                        <TableCell className="text-right">
                          {rowActions(row)}
                        </TableCell>
                      )}
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          <div className="flex items-center justify-between text-[13px] text-muted-foreground">
            <span className="tabular-nums">총 {total.toLocaleString()}건</span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                이전
              </Button>
              <span className="tabular-nums">
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                다음
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
