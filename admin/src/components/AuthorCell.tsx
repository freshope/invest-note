import type { ReactNode } from "react";

// 작성자/회원 표시 공용 셀 — 아바타(없으면 이니셜) + 이름.
// 이름이 없으면 fallback 을 호출부가 계산해 넘긴다(board: "회원 미상", users: "-").
// 주의: raw user_id(UUID)를 fallback 으로 넘기지 말 것 — 프로필 미수집 작성자가 UUID 로 노출됨.
// 테이블 셀·인라인 텍스트 양쪽에서 쓰이므로 inline-flex + align-middle.
export function AuthorCell({
  avatarUrl,
  displayName,
  fallback,
}: {
  avatarUrl?: string | null;
  displayName?: string | null;
  fallback?: ReactNode;
}) {
  const name = displayName?.trim();
  return (
    <span className="inline-flex items-center gap-2 align-middle">
      {avatarUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={avatarUrl}
          alt=""
          className="h-6 w-6 rounded-full object-cover"
        />
      ) : (
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-muted text-[11px] text-muted-foreground">
          {name ? name[0]!.toUpperCase() : "?"}
        </span>
      )}
      <span>{name || fallback}</span>
    </span>
  );
}
