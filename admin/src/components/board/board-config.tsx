import type { BoardRow, BoardType } from "@/lib/api";
import type { Column } from "@/components/DataTablePage";
import { fmtText, fmtDateTime } from "@/lib/format";
import {
  boardStatusLabel,
  statementTypeLabel,
} from "@/components/board/constants";

function meta(row: BoardRow, key: string): unknown {
  return (row.metadata ?? {})[key];
}

// 상태 뱃지(타입별 어휘로 라벨).
function StatusBadge({ boardType, status }: { boardType: BoardType; status: string }) {
  return (
    <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-[12px] font-medium">
      {boardStatusLabel(boardType, status)}
    </span>
  );
}

const titleCol: Column<BoardRow> = {
  header: "제목",
  cell: (r) => fmtText(r.title),
};
const createdCol: Column<BoardRow> = {
  header: "작성일",
  cell: (r) => fmtDateTime(r.created_at),
};
const authorCol: Column<BoardRow> = {
  header: "작성자",
  cell: (r) => fmtText(r.user_id),
};

export interface BoardConfig {
  columns: Column<BoardRow>[];
  // "글 작성" 버튼 노출 여부(UI 어포던스 — BE 는 전 타입 작성 허용).
  canCreate: boolean;
}

// 목록은 구조가 동일(DataTablePage) → 타입별 차이는 컬럼·작성가능 여부뿐.
export const BOARD_CONFIG: Record<BoardType, BoardConfig> = {
  notice: {
    canCreate: true,
    columns: [
      titleCol,
      { header: "고정", cell: (r) => (r.is_pinned ? "📌" : "-") },
      createdCol,
    ],
  },
  feedback: {
    canCreate: false,
    columns: [
      titleCol,
      authorCol,
      {
        header: "상태",
        cell: (r) => <StatusBadge boardType="feedback" status={r.status} />,
      },
      createdCol,
    ],
  },
  bug_report: {
    canCreate: false,
    columns: [
      titleCol,
      authorCol,
      {
        header: "상태",
        cell: (r) => <StatusBadge boardType="bug_report" status={r.status} />,
      },
      createdCol,
    ],
  },
  broker_statement: {
    canCreate: false,
    columns: [
      titleCol,
      { header: "증권사", cell: (r) => fmtText(meta(r, "broker")) },
      { header: "국가", cell: (r) => fmtText(meta(r, "country")) },
      { header: "제보유형", cell: (r) => statementTypeLabel(meta(r, "type")) },
      {
        header: "상태",
        cell: (r) => <StatusBadge boardType="broker_statement" status={r.status} />,
      },
      createdCol,
    ],
  },
};
