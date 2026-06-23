import {
  Megaphone,
  MessageSquare,
  Bug,
  FileText,
  type LucideIcon,
} from "lucide-react";
import type { BoardType } from "@/lib/api";

// board_type 표시 라벨(필터·컬럼·다이얼로그 공용).
export const BOARD_TYPES: { value: BoardType; label: string }[] = [
  { value: "notice", label: "공지" },
  { value: "feedback", label: "사용자 의견" },
  { value: "bug_report", label: "오류 신고" },
  { value: "broker_statement", label: "거래내역서 제출" },
];

export function boardTypeLabel(t: string): string {
  return BOARD_TYPES.find((b) => b.value === t)?.label ?? t;
}

// 게시판별 아이콘(nav 메뉴·목록 디스크립터 공용). 순수 데이터 SSOT.
export const BOARD_TYPE_ICONS: Record<BoardType, LucideIcon> = {
  notice: Megaphone,
  feedback: MessageSquare,
  bug_report: Bug,
  broker_statement: FileText,
};

// 거래내역서 제보 유형(metadata.type) 라벨.
const STATEMENT_TYPE_LABELS: Record<string, string> = {
  unsupported_broker: "미지원 증권사",
  overseas_trade: "해외 거래",
};

export function statementTypeLabel(t: unknown): string {
  return typeof t === "string" ? STATEMENT_TYPE_LABELS[t] ?? t : "-";
}

// ── URL slug ↔ board_type 단일 출처 ──────────────────────────
// nav·라우트·활성표시가 전부 여기서 파생. URL 은 하이픈, type 은 언더스코어.
export const BOARD_TYPE_SLUGS: Record<BoardType, string> = {
  notice: "notice",
  feedback: "feedback",
  bug_report: "bug-report",
  broker_statement: "broker-statement",
};

export function boardTypeToSlug(t: BoardType): string {
  return BOARD_TYPE_SLUGS[t];
}

export function slugToBoardType(slug: string): BoardType | null {
  const entry = (Object.entries(BOARD_TYPE_SLUGS) as [BoardType, string][]).find(
    ([, s]) => s === slug,
  );
  return entry ? entry[0] : null;
}

// status 어휘는 BE 자유 텍스트 — 어드민에서 쓰는 작은 집합(FE 선정).
// 게시판 성격별로 다른 어휘를 노출한다(공지는 상태 미사용).
export const BOARD_STATUSES_BY_TYPE: Record<
  BoardType,
  { value: string; label: string }[]
> = {
  notice: [],
  feedback: [
    { value: "open", label: "열림" },
    { value: "resolved", label: "해결됨" },
  ],
  bug_report: [
    { value: "open", label: "열림" },
    { value: "closed", label: "닫힘" },
    { value: "resolved", label: "해결됨" },
  ],
  broker_statement: [
    { value: "open", label: "검토중" },
    { value: "resolved", label: "완료" },
    { value: "closed", label: "반려" },
  ],
};

// status 값(open/closed/resolved)은 타입별 라벨이 다르므로 board_type 기준으로 조회.
// 어휘 밖 값(향후 app-side 작성 등)은 원문 표시.
export function boardStatusLabel(boardType: BoardType, s: string): string {
  return BOARD_STATUSES_BY_TYPE[boardType].find((x) => x.value === s)?.label ?? s;
}

// React Query 목록 키. board_type 별로 캐시 분리 + invalidate 컨벤션 통일.
// ⚠️ 모든 invalidate 사이트가 이 함수로 키를 만들어야 prefix 매칭이 성립한다.
export function boardListKey(boardType: BoardType): readonly unknown[] {
  return ["admin", `boards:${boardType}`];
}

// 상세 키.
export function boardDetailKey(postId: string): readonly unknown[] {
  return ["admin", "board-detail", postId];
}
