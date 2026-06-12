import { cn } from "@/lib/utils";
import { formatMoney } from "@/lib/format";

interface MoneyTextProps {
  /** KRW 값(primary). null 이면 "-". */
  krw: number | null;
  /** native 통화 값(보조 표시용). currency 가 KRW 가 아니고 값이 있으면 괄호로 병기. */
  native?: number | null;
  /** 거래 통화(KRW|USD). KRW 면 보조 표시 없음. */
  currency?: string;
  className?: string;
  /** 보조(달러) 표시 스타일. */
  nativeClassName?: string;
}

/**
 * 금액 표시 — 원화(primary) + 해외주식이면 native(달러) 보조 병기. 예: "1,095,500원 ($716.07)".
 * 기본 표시 통화를 원화로 통일하고, 해외는 달러를 작게 괄호로 보조 표시한다.
 */
export function MoneyText({
  krw,
  native,
  currency = "KRW",
  className,
  nativeClassName,
}: MoneyTextProps) {
  if (krw === null) return <span className={className}>-</span>;
  const primary = formatMoney(krw, "KRW");
  const showNative = currency !== "KRW" && native != null;
  return (
    <span className={className}>
      {primary}
      {showNative && (
        <span className={cn("text-muted-foreground font-normal", nativeClassName)}>
          {" "}({formatMoney(native as number, currency)})
        </span>
      )}
    </span>
  );
}
