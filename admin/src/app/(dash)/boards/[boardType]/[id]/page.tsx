"use client";

import { useParams, notFound } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { adminApi } from "@/lib/api";
import { ApiErrorState } from "@/components/ApiErrorState";
import { boardDetailKey, slugToBoardType } from "@/components/board/constants";
import { NoticeDetail } from "@/components/board/details/NoticeDetail";
import { TriageDetail } from "@/components/board/details/TriageDetail";
import { StatementDetail } from "@/components/board/details/StatementDetail";

export default function BoardDetailPage() {
  const params = useParams<{ boardType: string; id: string }>();
  const slug = params.boardType;
  const boardType = slugToBoardType(slug);
  if (!boardType) notFound();

  const { data, isLoading, error } = useQuery({
    queryKey: boardDetailKey(params.id),
    queryFn: () => adminApi.boards.get(params.id),
    enabled: !!params.id,
  });

  if (error) return <ApiErrorState error={error} />;
  if (isLoading || !data) {
    return <p className="text-sm text-muted-foreground">불러오는 중...</p>;
  }

  // 글의 실제 board_type 이 URL slug 와 다르면(주소 직접 변경 등) 404.
  if (data.board_type !== boardType) notFound();

  switch (boardType) {
    case "notice":
      return <NoticeDetail data={data} slug={slug} />;
    case "broker_statement":
      return <StatementDetail data={data} slug={slug} />;
    case "feedback":
    case "bug_report":
      return <TriageDetail data={data} slug={slug} />;
  }
}
