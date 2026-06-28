import { STORAGE_KEYS } from "@/lib/constants/storage";

/**
 * 게시판 인앱 알림의 "읽음" 상태를 기기 localStorage 에만 기록한다(BE 읽음 테이블 없음).
 * - ackedResolvedPostIds: 진입 팝업을 이미 본 resolved post-id 집합 → 팝업 1회 dedup.
 *   updated_at 은 status 외 수정에도 갱신되므로 시각이 아니라 id 집합으로 처리한다.
 * - lastReadMyPost: 글별 마지막 상세 열람 시각 맵(postId→ISO). 상세를 열 때 그 글만 기록 →
 *   글별 읽기 점 독립 해제. 안읽음 판정(최신활동 비교)은 board-post.ts isMyPostUnread.
 * - lastSeenNotice: 공지 마지막 확인 시각. 최신 notice created_at 과 비교.
 *
 * SSR/네이티브 cold start 에서도 안전하게 window 가드 + try-catch 로 감싼다(실패 시 no-op).
 */

function readRaw(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeRaw(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // private 모드/용량 초과 등 — 읽음 상태 기록 실패는 무시(no-op).
  }
}

// ── 진입 팝업 dedup (resolved post-id 집합) ───────────────────────────────

export function getAckedResolvedPostIds(): string[] {
  const raw = readRaw(STORAGE_KEYS.ACKED_RESOLVED_POST_IDS);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((v): v is string => typeof v === "string") : [];
  } catch {
    return [];
  }
}

export function hasAckedResolvedPost(id: string): boolean {
  return getAckedResolvedPostIds().includes(id);
}

export function addAckedResolvedPost(id: string): void {
  const ids = getAckedResolvedPostIds();
  if (ids.includes(id)) return;
  writeRaw(STORAGE_KEYS.ACKED_RESOLVED_POST_IDS, JSON.stringify([...ids, id]));
}

// ── 글별 마지막 상세 열람 시각 (postId→ISO 맵) ─────────────────────────────

/** 전체 read map(postId→ISO) 1회 읽기. 다건 판정 시 글마다 재파싱 대신 이걸 주입. */
export function getLastReadMyPostMap(): Record<string, string> {
  const raw = readRaw(STORAGE_KEYS.LAST_READ_MY_POST);
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as Record<string, string>)
      : {};
  } catch {
    return {};
  }
}

export function getLastReadMyPost(postId: string): string | null {
  return getLastReadMyPostMap()[postId] ?? null;
}

export function setLastReadMyPost(
  postId: string,
  iso: string = new Date().toISOString(),
): void {
  const map = getLastReadMyPostMap();
  map[postId] = iso;
  writeRaw(STORAGE_KEYS.LAST_READ_MY_POST, JSON.stringify(map));
}

// ── 공지 마지막 확인 시각 ─────────────────────────────────────────────────

export function getLastSeenNotice(): string | null {
  return readRaw(STORAGE_KEYS.LAST_SEEN_NOTICE);
}

export function setLastSeenNotice(iso: string = new Date().toISOString()): void {
  writeRaw(STORAGE_KEYS.LAST_SEEN_NOTICE, iso);
}
