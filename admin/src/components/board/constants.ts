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

// status 어휘는 BE 자유 텍스트 — 어드민에서 쓰는 작은 집합(FE 선정).
export const BOARD_STATUSES: { value: string; label: string }[] = [
  { value: "open", label: "열림" },
  { value: "closed", label: "닫힘" },
  { value: "resolved", label: "해결됨" },
];

export function boardStatusLabel(s: string): string {
  return BOARD_STATUSES.find((b) => b.value === s)?.label ?? s;
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
