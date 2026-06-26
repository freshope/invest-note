"use client";

import { useParams, notFound } from "next/navigation";
import Link from "next/link";
import { adminApi } from "@/lib/api";
import { DataTablePage } from "@/components/DataTablePage";
import { Button } from "@/components/base/Button";
import {
  boardTypeLabel,
  slugToBoardType,
} from "@/components/board/constants";
import { BOARD_CONFIG } from "@/components/board/board-config";
import { BoardCreateDialog } from "../BoardCreateDialog";

export default function BoardListPage() {
  const params = useParams<{ boardType: string }>();
  const boardType = slugToBoardType(params.boardType);
  if (!boardType) notFound();

  const config = BOARD_CONFIG[boardType];
  const label = boardTypeLabel(boardType);

  return (
    <DataTablePage
      // 게시판 전환 시 같은 [boardType] 페이지가 재사용되므로 key 로 remount →
      // DataTablePage 내부 page/검색 상태 초기화 + 이전 게시판 행 플래시 방지.
      key={boardType}
      title={label}
      // queryKey 에 board_type 합성 → 캐시 분리 + invalidate 컨벤션(boardListKey)과 일치.
      queryKey={`boards:${boardType}`}
      fetchList={(p) => adminApi.boards.list({ ...p, board_type: boardType })}
      columns={config.columns}
      searchPlaceholder="제목 검색"
      toolbar={
        config.canCreate ? <BoardCreateDialog boardType={boardType} /> : undefined
      }
      rowActions={(row) => (
        <Button asChild variant="outline" size="sm">
          <Link href={`/boards/${params.boardType}/${row.id}`}>상세</Link>
        </Button>
      )}
    />
  );
}
