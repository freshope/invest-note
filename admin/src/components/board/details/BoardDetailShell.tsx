"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import type { BoardDetail } from "@/lib/api";
import { Button } from "@/components/base/Button";
import { BoardDeleteButton } from "@/components/board/BoardDeleteButton";

// 상세 공통 chrome: 뒤로가기(해당 게시판 목록) + 삭제. 본문은 children 로 조합.
export function BoardDetailShell({
  data,
  slug,
  children,
}: {
  data: BoardDetail;
  slug: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Button asChild variant="outline" size="sm">
          <Link href={`/boards/${slug}`}>← 목록</Link>
        </Button>
        <BoardDeleteButton postId={data.id} boardType={data.board_type} />
      </div>
      {children}
    </div>
  );
}
