"use client";

import { useState } from "react";
import Link from "next/link";
import { adminApi, type BoardRow, type BoardType } from "@/lib/api";
import { DataTablePage, type Column } from "@/components/DataTablePage";
import { Button } from "@/components/base/Button";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/base/Select";
import { fmtText, fmtDateTime } from "@/lib/format";
import {
  BOARD_TYPES,
  boardTypeLabel,
  boardStatusLabel,
} from "@/components/board/constants";
import { BoardCreateDialog } from "./BoardCreateDialog";

const columns: Column<BoardRow>[] = [
  { header: "제목", cell: (r) => fmtText(r.title) },
  { header: "게시판", cell: (r) => boardTypeLabel(r.board_type) },
  { header: "상태", cell: (r) => boardStatusLabel(r.status) },
  { header: "고정", cell: (r) => (r.is_pinned ? "📌" : "-") },
  { header: "작성일", cell: (r) => fmtDateTime(r.created_at) },
];

export default function BoardsPage() {
  const [boardType, setBoardType] = useState<BoardType>("notice");

  return (
    <DataTablePage
      // key 로 board_type 전환 시 remount → 내부 page/q 초기화.
      key={boardType}
      title="게시판"
      // queryKey 에 board_type 합성 → 캐시 분리 + invalidate 컨벤션(boardListKey)과 일치.
      queryKey={`boards:${boardType}`}
      fetchList={(params) => adminApi.boards.list({ ...params, board_type: boardType })}
      columns={columns}
      searchPlaceholder="제목 검색"
      toolbar={
        <div className="flex items-center gap-2">
          <Select
            value={boardType}
            onValueChange={(v) => setBoardType(v as BoardType)}
          >
            <SelectTrigger className="w-[160px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {BOARD_TYPES.map((b) => (
                <SelectItem key={b.value} value={b.value}>
                  {b.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <BoardCreateDialog defaultBoardType={boardType} />
        </div>
      }
      rowActions={(row) => (
        <Button asChild variant="outline" size="sm">
          <Link href={`/boards/${row.id}`}>상세</Link>
        </Button>
      )}
    />
  );
}
