interface Props {
  tickers: string[];
}

export function MissingQuoteBadge({ tickers }: Props) {
  if (tickers.length === 0) return null;
  return (
    <p className="text-[11px] text-muted-foreground">
      시세 미조회: {tickers.slice(0, 3).join(", ")}
      {tickers.length > 3 && ` 외 ${tickers.length - 3}개`} — 평가금액 제외됨
    </p>
  );
}
