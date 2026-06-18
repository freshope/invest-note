import { ApiError } from "@/lib/api";

// 데이터 호출 실패 공통 표시. 비-admin(allowlist 밖)은 API 가 403 을 반환하므로
// 셸에 진입해도 데이터가 안 보이고 이 안내가 뜬다(spec 목표 #2).
export function ApiErrorState({ error }: { error: unknown }) {
  const status = error instanceof ApiError ? error.status : undefined;
  const message =
    status === 403
      ? "이 계정은 어드민 권한이 없습니다(ADMIN_EMAILS allowlist 외)."
      : status === 503
        ? "어드민 DB가 설정되지 않았습니다(ADMIN_DATABASE_URL)."
        : error instanceof Error
          ? error.message
          : "데이터를 불러오지 못했습니다.";

  return (
    <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-[14px] text-destructive">
      {message}
    </div>
  );
}
