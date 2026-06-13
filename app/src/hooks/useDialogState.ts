import { useCallback, useState } from "react";

/**
 * 삭제/저장 등 비동기 액션을 가진 다이얼로그용 상태 묶음.
 * `run`은 try/catch/finally를 캡슐화하고 성공 시 닫고, 실패 시 메시지를 보관한다.
 */
export function useDialogState() {
  const [open, setOpenState] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 다이얼로그가 새로 열릴 때마다 이전 시도의 에러/대기 상태를 자동 초기화한다.
  const setOpen = useCallback((next: boolean) => {
    if (next) {
      setError(null);
      setPending(false);
    }
    setOpenState(next);
  }, []);

  const run = useCallback(
    async (fn: () => Promise<void>, fallbackMessage = "오류가 발생했습니다.") => {
      setError(null);
      setPending(true);
      try {
        await fn();
        setOpenState(false);
      } catch (err) {
        setError(err instanceof Error ? err.message : fallbackMessage);
      } finally {
        setPending(false);
      }
    },
    [],
  );

  return { open, setOpen, pending, error, run };
}
