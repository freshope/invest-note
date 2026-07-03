interface ErrorStateProps {
  message?: string;
  onRetry?: () => void | Promise<unknown>;
}

export function ErrorState({ message = "데이터를 불러오지 못했어요.", onRetry }: ErrorStateProps) {
  // fetchQuery 기반 refetch 는 네트워크 실패 시 promise 를 reject 한다. onClick 이 반환값을
  // 버리면 unhandledrejection("Failed to fetch")으로 표면화되므로 여기서 흡수한다.
  // 에러는 useQuery observer 의 isError 로 이미 UI(이 ErrorState)에 반영되어 재노출된다.
  const handleRetry = () => {
    void Promise.resolve(onRetry?.()).catch(() => {});
  };
  return (
    <div className="px-5 pt-6 text-center space-y-3">
      <p className="text-[13px] text-muted-foreground">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={handleRetry}
          className="text-primary text-[13px] font-medium"
        >
          다시 시도
        </button>
      )}
    </div>
  );
}
