import type {
  MyPost,
  MyPostAttachment,
  MyPostBoardType,
  MyPostStatus,
} from "@/lib/api-client";
import { getLastReadMyPost } from "@/lib/board-seen";

/** 유형 라벨. */
export const TYPE_LABEL: Record<MyPostBoardType, string> = {
  broker_statement: "거래내역서 제보",
  feedback: "의견",
  bug_report: "오류 신고",
};

/**
 * 내 제보/문의 글의 표시 가공 + 읽기 상태 파생.
 * 단방향 의존: board-post → board-seen(+api-client 타입). board-seen 은 board-post 를 import 하지 않는다.
 */

/** 제목 선행 `[type]` prefix 제거(`[unsupported_broker] 토스증권` → `토스증권`). */
export function stripTypePrefix(title: string): string {
  return title.replace(/^\s*\[[^\]]*\]\s*/, "").trim();
}

/**
 * 목록/상세에 보일 제목. broker_statement 는 증권사명(metadata.broker) 우선,
 * 그 외/누락 시 prefix 제거한 title. (raw title 직접 노출 금지 — `[type]` 누출 방지)
 */
export function getPostDisplayTitle(post: MyPost): string {
  if (post.board_type === "broker_statement" && post.metadata.broker) {
    return post.metadata.broker;
  }
  return stripTypePrefix(post.title);
}

/**
 * 읽기 점: 어드민 활동(답변 또는 상태변경)이 있고, 그게 마지막 상세 열람 이후이면 안읽음.
 * - 어드민 활동이 전혀 없는 글(status='open' + is_admin 댓글 0 = 갓 쓴 본인 글)은 점 없음.
 * - 상태변경 신호는 status!=='open'(상태값) + updated_at 을 활동시각으로 본다. status 미변경 글은
 *   updated_at(본문 편집 잡음)을 무시하고 최신 어드민 댓글 시각만 활동으로 본다.
 * - 시각 비교는 `Date.getTime()` 수치로(BE `+00:00` vs 클라 `Z` 사전식 비교 버그 회피).
 * - 다건 판정 시 lastReadMap 주입(글마다 localStorage 재파싱 방지). 미주입 시 단건 조회.
 */
export function isMyPostUnread(
  post: MyPost,
  lastReadMap?: Record<string, string>,
): boolean {
  const hasAdminComment = post.comments.some((c) => c.is_admin);
  const statusChanged = post.status !== "open"; // resolved | closed
  if (!hasAdminComment && !statusChanged) return false;
  let latestAdminMs = 0;
  for (const c of post.comments) {
    if (c.is_admin) {
      latestAdminMs = Math.max(latestAdminMs, new Date(c.created_at).getTime());
    }
  }
  const statusMs = statusChanged ? new Date(post.updated_at).getTime() : 0;
  const activityMs = Math.max(statusMs, latestAdminMs);
  const lastRead = lastReadMap
    ? lastReadMap[post.id]
    : getLastReadMyPost(post.id);
  if (!lastRead) return true;
  return activityMs > new Date(lastRead).getTime();
}

/** 상태 칩 메타(라벨 + 클래스). PnL 색 아님(검토중/완료/반려). */
export const STATUS_META: Record<
  MyPostStatus,
  { label: string; className: string }
> = {
  open: { label: "검토중", className: "bg-muted text-muted-foreground" },
  resolved: { label: "완료", className: "bg-primary/10 text-primary" },
  closed: { label: "반려", className: "bg-muted text-muted-foreground/70" },
};

/**
 * 이미지 첨부 판정. content_type(image/*) 우선 + 확장자 폴백.
 * 모바일 피커/카메라가 File.type 을 빈 값/`application/octet-stream` 으로 주는 경우가 흔해
 * mime 만으로는 실제 스크린샷이 다운로드 행으로 빠진다 → BE 가 확장자를 실제 게이트로 삼는 것과
 * 동일하게 확장자로도 판정한다.
 */
export function isImageAttachment(a: MyPostAttachment): boolean {
  return (
    a.content_type?.startsWith("image/") === true ||
    /\.(png|jpe?g|webp|heic)$/i.test(a.original_name)
  );
}

/** 바이트 → 사람용 크기 문자열(첨부 다운로드 표시). */
export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return `${value >= 10 || i === 0 ? Math.round(value) : value.toFixed(1)}${units[i]}`;
}
