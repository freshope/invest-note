import { formatFxRate } from "@/lib/format";

/**
 * 해외(US) 거래의 역산 환율 = 체결 원화 / (가격 × 수량).
 * 가격·수량 곱이 0 이하면 null(역산 불가). 제출 시 exchange_rate 역산과
 * 힌트 미리보기가 공유하는 단일 소스.
 */
export function impliedExchangeRate(
  amountKrw: number,
  price: number,
  qty: number,
): number | null {
  const totalNative = (price || 0) * (qty || 0);
  if (totalNative <= 0) return null;
  return amountKrw / totalNative;
}

/**
 * 역산 환율 힌트 텍스트(등록/수정 폼 공유). 체결 원화 미입력 시 안내 문구,
 * 입력 시 역산 환율 + (현재 시세 환율). 모두 formatFxRate(₩+2자리)로 통일.
 */
export function fxHintText(
  amountKrw: number,
  price: number,
  qty: number,
  usdkrw: number | null,
): string {
  const implied = (amountKrw || 0) > 0 ? impliedExchangeRate(amountKrw, price, qty) : null;
  const base =
    implied != null ? `역산 환율 ≈ ${formatFxRate(implied)}` : "가격·수량 입력 시 역산 환율 표시";
  return usdkrw != null ? `${base} · 현재 시세 ${formatFxRate(usdkrw)}` : base;
}
