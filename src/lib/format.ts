/** ₩1,234,567 형식 */
export function formatKRW(value: number): string {
  return `₩${Math.abs(value).toLocaleString('ko-KR')}`
}

/** +1.23% / -0.45% 형식 */
export function formatPercent(value: number): string {
  const sign = value >= 0 ? '+' : '-'
  return `${sign}${Math.abs(value).toFixed(2)}%`
}

/** 수익 색상 클래스 (한국 관행: 상승=빨강, 하락=파랑) */
export function profitColorClass(value: number): string {
  if (value > 0) return 'text-[#F04452]'
  if (value < 0) return 'text-[#1B6AC9]'
  return 'text-[#8B95A1]'
}

/** 금액 + 수익률 복합 표시 */
export function formatPnL(amount: number, percent: number): { amount: string; percent: string; colorClass: string } {
  const sign = amount >= 0 ? '+' : '-'
  return {
    amount: `${sign}${formatKRW(Math.abs(amount))}`,
    percent: formatPercent(percent),
    colorClass: profitColorClass(amount),
  }
}

/** 날짜 YYYY.MM.DD */
export function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`
}

/** 숫자 입력 시 콤마 포맷 */
export function formatNumberInput(value: string): string {
  const num = value.replace(/[^0-9.]/g, '')
  const parts = num.split('.')
  parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return parts.join('.')
}

/** 콤마 제거 후 숫자 반환 */
export function parseNumberInput(value: string): number {
  return parseFloat(value.replace(/,/g, '')) || 0
}
