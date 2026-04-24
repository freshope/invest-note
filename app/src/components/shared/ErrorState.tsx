interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
}

export function ErrorState({ message = "데이터를 불러오지 못했어요.", onRetry }: ErrorStateProps) {
  return (
    <div className="px-5 pt-6 text-center space-y-3">
      <p className="text-[13px] text-muted-foreground">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="text-primary text-[13px] font-medium"
        >
          다시 시도
        </button>
      )}
    </div>
  );
}
