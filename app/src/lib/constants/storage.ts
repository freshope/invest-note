const PREFIX = "invest-note:";

export const STORAGE_KEYS = {
  LAST_ACCOUNT_ID: `${PREFIX}last-account-id`,
  // 게시판 인앱 알림 읽음 상태(기기 로컬). board-seen.ts 참고.
  ACKED_RESOLVED_POST_IDS: `${PREFIX}board:acked-resolved-post-ids`,
  // 글별 마지막 상세 열람 시각 맵(postId→ISO). 구 type별 last-seen-my-posts 대체.
  LAST_READ_MY_POST: `${PREFIX}board:last-read-my-post`,
  LAST_SEEN_NOTICE: `${PREFIX}board:last-seen-notice`,
} as const;
