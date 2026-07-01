import type { FieldErrors } from "react-hook-form";
import { toast } from "sonner";
import { getFirstFormError } from "./utils";

// 긴 폼에서 제출 실패 시 에러난 필드가 스크롤 밖이면 안 보이는 문제(모바일)를 toast 로 해결한다.
// FullScreenPanel(z-100) 위에 뜨도록 sonner 기본 z-index(999999999)에 의존.

/** invalid submit 핸들러 — 첫 필드 검증 에러를 toast 로 알린다. handleSubmit(onSubmit, toastFirstFormError). */
export function toastFirstFormError(errors: FieldErrors) {
  const message = getFirstFormError(errors);
  if (message) toast.error(message);
}

/** 제출/서버 실패를 toast 로 알린다. catch 블록에서 사용. */
export function toastSubmitError(err: unknown, fallback = "저장에 실패했습니다.") {
  toast.error(err instanceof Error ? err.message : fallback);
}
